"""Bounded, single-process job supervisor. PDF/LLM work runs in killable children."""
import collections
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time

LOG = logging.getLogger('gunicorn.error')
TERMINAL = {'completed', 'failed', 'expired'}


class JobManager:
    def __init__(self, root, timeout=120, retention=3600, command=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Previous-process credentials are deliberately not recovered.
        for path in self.root.iterdir():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        self.timeout, self.retention = timeout, retention
        self.command = command or [sys.executable, str(Path(__file__).with_name('job_worker.py'))]
        self.jobs = {}
        self.queue = collections.deque()
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name='resume-jobs')
        self.thread.start()

    def reserve(self):
        with self.lock:
            active = sum(j['state'] not in TERMINAL for j in self.jobs.values())
            if active >= 3:
                return None
            job_id, token = secrets.token_hex(16), secrets.token_urlsafe(32)
            now = time.time()
            job = dict(id=job_id, digest=hashlib.sha256(token.encode()).hexdigest(),
                       state='uploading', stage='reading', created=now, expires_at=now+self.retention,
                       deadline=time.monotonic()+self.timeout, result=None, process=None)
            self.jobs[job_id] = job
            (self.root/job_id).mkdir()
            return job_id, token

    def submit(self, job_id, manifest):
        with self.lock:
            job = self.jobs[job_id]
            path = self.root/job_id
            (path/'input.json').write_text(json.dumps(manifest), encoding='utf-8')
            job.update(state='queued', stage='queued')
            self.queue.append(job_id)
            self.wake.set()

    def authorized(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            digest = hashlib.sha256(token.encode()).hexdigest()
            return job is not None and secrets.compare_digest(job['digest'], digest)

    def discard(self, job_id):
        with self.lock:
            job = self.jobs.pop(job_id, None)
            if job and job.get('process'):
                self._terminate(job['process'])
            shutil.rmtree(self.root/job_id, ignore_errors=True)

    @staticmethod
    def _terminate(proc):
        try:
            # Also kill Chromium descendants, even when the Python child exited.
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=2)
        except ProcessLookupError:
            pass

    def status(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job['state'] not in TERMINAL and time.monotonic() >= job['deadline']:
                self._fail(job, 'timeout', '任务等待或处理超过 120 秒，请稍后重试。')
            if job['state'] == 'running':
                try:
                    progress = json.loads((self.root/job_id/'progress.json').read_text())
                    job['stage'] = progress['stage']
                except (OSError, ValueError, KeyError):
                    pass
            queued = [i for i in self.queue if i in self.jobs and self.jobs[i]['state']=='queued']
            return dict(job_id=job_id, state=job['state'], stage=job['stage'],
                        queue_position=queued.index(job_id)+1 if job_id in queued else 0,
                        elapsed_seconds=round(time.time()-job['created']),
                        expires_at=job['expires_at'], result=job['result'])

    def _fail(self, job, code, message):
        if job['process']:
            self._terminate(job['process'])
        job.update(state='failed', stage='failed', result={'code':code, 'message':message})
        shutil.rmtree(self.root/job['id'], ignore_errors=True)
        LOG.info('resume_job state=failed code=%s duration=%.2f', code, time.time()-job['created'])

    def cleanup(self):
        with self.lock:
            now = time.time()
            for job_id, job in list(self.jobs.items()):
                if now >= job['expires_at']:
                    self.discard(job_id)

    def _loop(self):
        cleanup_at = time.monotonic()+300
        while not self.stopping.is_set():
            if time.monotonic() >= cleanup_at:
                self.cleanup()
                cleanup_at = time.monotonic()+300
            with self.lock:
                job_id = self.queue.popleft() if self.queue else None
                job = self.jobs.get(job_id)
                if job and job['state']=='queued':
                    if time.monotonic() >= job['deadline']:
                        self._fail(job, 'timeout', '任务等待超过 120 秒，请稍后重试。')
                        job = None
                    else:
                        try:
                            proc = subprocess.Popen(self.command+[str(self.root/job_id)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                            job.update(state='running', stage='reading', process=proc)
                        except OSError:
                            self._fail(job, 'unavailable', '处理服务暂不可用，请稍后重试。')
                            job = None
                else:
                    job = None
            if not job:
                self.wake.wait(.2)
                self.wake.clear()
                continue
            while not self.stopping.is_set():
                with self.lock:
                    if job_id not in self.jobs or job['state'] in TERMINAL:
                        break
                    if time.monotonic() >= job['deadline']:
                        self._fail(job, 'timeout', '任务等待或处理超过 120 秒，请稍后重试。')
                        break
                    if proc.poll() is not None:
                        try:
                            result = json.loads((self.root/job_id/'result.json').read_text())
                            if proc.returncode or not result.get('ok'):
                                LOG.warning('resume_job worker_exit=%s error_type=%s',proc.returncode,result.get('diagnostic','unknown'))
                                self._fail(job, result.get('code','generation_failed'), result.get('message','生成失败，请重试。'))
                            else:
                                job.update(state='completed', stage='completed', result=result)
                                LOG.info('resume_job state=completed duration=%.2f pages=%s timings=%s warning=%s',
                                         time.time()-job['created'], result['pages'], result['timings'], result['verification']['needs_review'])
                        except (OSError, ValueError, KeyError):
                            LOG.warning('resume_job worker_exit=%s no_result=true',proc.returncode)
                            self._fail(job, 'generation_failed', '生成未完成，请重试。')
                        finally:
                            self._terminate(proc)
                        break
                self.stopping.wait(.2)

    def close(self):
        self.stopping.set()
        self.wake.set()
        with self.lock:
            for job in self.jobs.values():
                if job['process']:
                    self._terminate(job['process'])
        self.thread.join(timeout=3)
