import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from app import create_app, validate_pdf, MAX_FILE
from job_runner import JobManager
from job_worker import validate_content, verify
from tests.fixtures import pdf_bytes


class API(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'JOB_ROOT':self.temp.name})
        # Worker fixture exercises process supervision without making API calls.
        self.script=Path(self.temp.name).parent/(Path(self.temp.name).name+'-worker.py')
        self.script.write_text("import sys,time,json\nfrom pathlib import Path\np=Path(sys.argv[1]); time.sleep(.3)\n(p/'result.json').write_text(json.dumps({'ok':True,'pages':1,'timings':{},'verification':{'needs_review':False}}))\n(p/'output.pdf').write_bytes(b'%PDF-test')\n(p/'page-1.png').write_bytes(b'preview')\n")
        self.manager=JobManager(self.temp.name,command=[sys.executable,str(self.script)])
        self.app.extensions['jobs']=self.manager
        self.client=self.app.test_client()
    def tearDown(self):
        self.manager.close(); self.temp.cleanup(); self.script.unlink(missing_ok=True)
    def submit(self,kind='short'):
        return self.client.post('/api/jobs',data={'resume':(io.BytesIO(pdf_bytes(kind)),'resume.pdf'),'template_id':'minimal'})
    def wait(self,job):
        h={'X-Job-Token':job['token']}
        for _ in range(60):
            r=self.client.get('/api/jobs/'+job['job_id'],headers=h)
            if r.json['state'] in ('completed','failed'): return r.json
            time.sleep(.05)
        self.fail('job never completed')
    def test_full_lifecycle_and_credentials(self):
        r=self.submit(); self.assertEqual(r.status_code,202); job=r.json
        url='/api/jobs/'+job['job_id']; h={'X-Job-Token':job['token']}
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get(url,headers={'X-Job-Token':'wrong'}).status_code,404)
        self.assertEqual(self.wait(job)['state'],'completed')
        with self.client.get('/api/download/'+job['job_id'],headers=h) as response:
            self.assertEqual(response.status_code,200)
        with self.client.get('/api/preview/'+job['job_id']+'/1',headers=h) as response:
            self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/preview/'+job['job_id']+'/2',headers=h).status_code,404)
        self.assertEqual(self.client.get(url,headers=h).headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.delete(url,headers=h).status_code,204)
        self.assertFalse((Path(self.temp.name)/job['job_id']).exists())
        self.assertEqual(self.client.get(url,headers=h).status_code,404)
    def test_health_responsive_and_queue_bounded(self):
        jobs=[self.submit() for _ in range(3)]
        self.assertTrue(all(r.status_code==202 for r in jobs))
        self.assertEqual(self.submit().status_code,429)
        start=time.monotonic(); self.assertEqual(self.client.get('/health').status_code,200)
        self.assertLess(time.monotonic()-start,.2)
        self.assertEqual(self.wait(jobs[0].json)['state'],'completed')
    def test_validation_errors_release_slots(self):
        for kind in ('damaged','encrypted','scan','pages','text_limit'):
            with self.subTest(kind=kind):
                r=self.submit(kind); self.assertEqual(r.status_code,400,r.json)
                self.assertEqual(len(self.manager.jobs),0)
        r=self.client.post('/api/jobs',data={'resume':(io.BytesIO(b'x'*(MAX_FILE+1)),'large.pdf'),'template_id':'minimal'})
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.manager.jobs),0)
    def test_timeout_releases_process_and_queue(self):
        self.manager.timeout=.08
        job=self.submit().json
        self.assertEqual(self.wait(job)['result']['code'],'timeout')
        self.assertFalse((Path(self.temp.name)/job['job_id']).exists())
    def test_expiration_and_restart(self):
        job=self.submit().json; self.wait(job)
        self.manager.jobs[job['job_id']]['expires_at']=0
        self.manager.cleanup()
        self.assertFalse(self.manager.authorized(job['job_id'],job['token']))
        self.assertFalse((Path(self.temp.name)/job['job_id']).exists())
    def test_user_file_not_served_as_static(self):
        self.assertEqual(self.client.get('/uploads/resume.pdf').status_code,404)
        self.assertEqual(self.client.get('/health').json['status'],'ok')


class Content(unittest.TestCase):
    def test_fixtures_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ('short','dense','two_pages','mixed'):
                p=Path(directory)/f'{kind}.pdf'; p.write_bytes(pdf_bytes(kind)); validate_pdf(p)
    def test_structure_type_validation(self):
        with self.assertRaises(ValueError): validate_content({'name':'x','sections':[{'entries':'bad'}]})
        with self.assertRaises(ValueError): validate_content({'name':None,'sections':[]})
    def test_content_mismatch_is_not_silent_success(self):
        v=verify('测试同学 2024 30%','测试同学 2025 30%','测试同学 2025')
        self.assertTrue(v['needs_review']); self.assertGreater(v['checks'][0]['missing_numbers'],0)
        self.assertFalse(verify('测试同学 2024','测试 同学\n2024','测试同学2024')['needs_review'])

if __name__=='__main__': unittest.main()
