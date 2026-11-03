"""PDF conversion HTTP API. Credentials and uploaded text never enter logs."""
import atexit
import json
import os
from pathlib import Path
import threading
import time

import fitz
from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from job_runner import JobManager

ROOT = Path(__file__).resolve().parent
MAX_FILE = 10*1024*1024


def validate_pdf(path, require_text=True):
    if path.stat().st_size > MAX_FILE:
        raise ValueError('每份 PDF 不能超过 10 MB。')
    try:
        with fitz.open(path) as doc:
            if not doc.is_pdf:
                raise ValueError('文件不是有效的 PDF。')
            if doc.needs_pass:
                raise ValueError('暂不支持加密 PDF，请先解除密码保护。')
            if not 1 <= len(doc) <= 10:
                raise ValueError('每份 PDF 需为 1 至 10 页。')
            text = '\n'.join(page.get_text() for page in doc)
            if len(text) > 20000:
                raise ValueError('PDF 文字超过 20,000 字符，请精简后重试。')
            if require_text and not text.strip():
                raise ValueError('未找到可提取的文字，暂不支持扫描版或图片 PDF（OCR）。')
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError) as exc:
        raise ValueError('PDF 损坏或无法读取，请重新导出后上传。') from exc


def create_app(test_config=None):
    app = Flask(__name__, static_folder=str(ROOT/'static'), static_url_path='')
    app.config.update(MAX_CONTENT_LENGTH=21*1024*1024,
                      JOB_ROOT=os.environ.get('JOB_ROOT', str(ROOT/'uploads'/'jobs')))
    if test_config:
        app.config.update(test_config)
    manager_lock = threading.Lock()

    def manager():
        with manager_lock:
            if 'jobs' not in app.extensions:
                app.extensions['jobs'] = JobManager(app.config['JOB_ROOT'])
                atexit.register(app.extensions['jobs'].close)
        return app.extensions['jobs']

    def auth(job_id):
        m = manager()
        token = request.headers.get('X-Job-Token', '')
        return m if m.authorized(job_id, token) else None

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; font-src 'self'; frame-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        response.headers['Cache-Control'] = 'no-store' if request.path.startswith('/api/') else 'public, max-age=0, must-revalidate'
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_):
        return jsonify(error='上传总大小超限，每份 PDF 不能超过 10 MB。', code='file_too_large'), 413

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/health')
    def health():
        return jsonify(status='ok', version='jobs-v1')

    @app.get('/api/templates')
    def templates():
        return jsonify(json.loads((ROOT/'static/templates/index.json').read_text()))

    @app.post('/api/jobs')
    def submit():
        m = manager()
        reserved = m.reserve()
        if not reserved:
            response = jsonify(error='当前有 3 个任务正在处理或等待，请稍后重试。', code='busy')
            response.status_code = 429
            response.headers['Retry-After'] = '10'
            return response
        job_id, token = reserved
        folder = Path(app.config['JOB_ROOT'])/job_id
        try:
            resume = request.files.get('resume')
            if not resume or not resume.filename:
                raise ValueError('请上传简历 PDF。')
            resume_path = folder/'resume.pdf'
            resume.save(resume_path)
            validate_pdf(resume_path)
            template_id = request.form.get('template_id')
            known = {t['id'] for t in json.loads((ROOT/'static/templates/index.json').read_text())}
            if template_id:
                if template_id not in known:
                    raise ValueError('模板不存在，请重新选择。')
                template_path = ROOT/'static/templates'/f'{template_id}.pdf'
            else:
                template = request.files.get('template')
                if not template or not template.filename:
                    raise ValueError('请选择内置模板或上传模板 PDF。')
                template_path = folder/'template.pdf'
                template.save(template_path)
                validate_pdf(template_path)
            m.submit(job_id, {'resume':str(resume_path), 'template':str(template_path), 'builtin':bool(template_id)})
            return jsonify(job_id=job_id, token=token, expires_at=m.jobs[job_id]['expires_at']), 202
        except ValueError as exc:
            m.discard(job_id)
            return jsonify(error=str(exc), code='invalid_pdf'), 400
        except RequestEntityTooLarge:
            m.discard(job_id)
            raise
        except Exception:
            m.discard(job_id)
            app.logger.error('job_submission_failed')
            return jsonify(error='暂时无法接收文件，请稍后重试。', code='unavailable'), 503

    @app.get('/api/jobs/<job_id>')
    def status(job_id):
        m = auth(job_id)
        if not m:
            return jsonify(error='任务不存在、已过期或服务已重启，请重新生成。', code='expired'), 404
        m.cleanup()
        status = m.status(job_id)
        if not status:
            return jsonify(error='任务已过期，请重新生成。', code='expired'), 404
        return jsonify(status)

    @app.delete('/api/jobs/<job_id>')
    def delete(job_id):
        m = auth(job_id)
        if not m:
            return jsonify(error='任务已过期或不存在。', code='expired'), 404
        m.discard(job_id)
        return '', 204

    def artifact(job_id, page=None):
        m = auth(job_id)
        if not m:
            return jsonify(error='结果已过期，请重新生成。', code='expired'), 404
        m.cleanup()
        status = m.status(job_id)
        if not status or status['state']!='completed':
            return jsonify(error='结果未就绪或已过期。', code='not_ready'), 409
        folder = Path(app.config['JOB_ROOT'])/job_id
        if page is not None:
            if not 1 <= page <= status['result']['pages']:
                return jsonify(error='页码不存在。'), 404
            path = folder/f'page-{page}.png'
            return send_file(path, mimetype='image/png') if path.exists() else (jsonify(error='结果已过期。'),404)
        path = folder/'output.pdf'
        return send_file(path, mimetype='application/pdf', as_attachment=True, download_name='简历.pdf') if path.exists() else (jsonify(error='结果已过期。'),404)

    @app.get('/api/download/<job_id>')
    def download(job_id):
        return artifact(job_id)

    @app.get('/api/preview/<job_id>/<int:page>')
    def preview(job_id, page):
        return artifact(job_id, page)


    return app


app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT',8080)))
