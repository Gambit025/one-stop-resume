"""Explicitly invoked synthetic-only deployment smoke/benchmark. No stored API keys."""
import argparse
import io
import json
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request
import uuid

import fitz
from tests.fixtures import pdf_bytes


def request(base,path,token=None,data=None,method=None,ctype=None):
    headers={'User-Agent':'OneStopResume-QA/1.0'}
    if token:headers['X-Job-Token']=token
    if ctype:headers['Content-Type']=ctype
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers,method=method),timeout=25) as response:
        return response.read()


def run(base,kind):
    boundary=uuid.uuid4().hex
    pdf=pdf_bytes(kind)
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="resume"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+pdf+(f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="template_id"\r\n\r\nminimal\r\n--{boundary}--\r\n').encode()
    start=time.monotonic()
    job=json.loads(request(base,'/api/jobs',data=body,method='POST',ctype='multipart/form-data; boundary='+boundary))
    status=None
    try:
        while time.monotonic()-start<135:
            status=json.loads(request(base,'/api/jobs/'+job['job_id'],job['token']))
            if status['state'] in ('completed','failed'):break
            time.sleep(2)
        duration=round(time.monotonic()-start,3)
        if status['state']!='completed':
            return {'fixture':kind,'ok':False,'seconds':duration,'error':status.get('result')}
        output=request(base,'/api/download/'+job['job_id'],job['token'])
        image=request(base,'/api/preview/'+job['job_id']+'/1',job['token'])
        assert output.startswith(b'%PDF-') and image.startswith(b'\x89PNG')
        with fitz.open(stream=output,filetype='pdf') as doc:
            text='\n'.join(p.get_text() for p in doc)
            assert ('Demo Candidate' if kind=='english_baseline' else '测试同学') in text, 'name missing in output'
            pages=len(doc)
        # Verify result routes deny access without credentials.
        try:
            request(base,'/api/download/'+job['job_id'])
            raise AssertionError('unprotected output')
        except urllib.error.HTTPError as exc:
            assert exc.code==404
        return {'fixture':kind,'ok':True,'seconds':duration,'pages':pages,'timings':status['result']['timings'],'verification':status['result']['verification']}
    finally:
        request(base,'/api/jobs/'+job['job_id'],job['token'],method='DELETE')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='https://one-stop-resume.onrender.com');parser.add_argument('--fixtures',nargs='+',default=['short']);parser.add_argument('--output',default='/tmp/resume-live-results.json');args=parser.parse_args()
    results=[]
    for kind in args.fixtures:
        try: result=run(args.base,kind)
        except Exception as exc: result={'fixture':kind,'ok':False,'error':type(exc).__name__+': '+str(exc)}
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2))
    if not all(r['ok'] for r in results):raise SystemExit(1)
