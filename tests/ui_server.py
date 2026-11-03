"""Local-only UI acceptance server; never copied into deployment image."""
import sys
from pathlib import Path
import tempfile
from app import create_app
from job_runner import JobManager

app=create_app({'JOB_ROOT':tempfile.mkdtemp(prefix='resume-ui-')})
app.extensions['jobs']=JobManager(app.config['JOB_ROOT'],command=[sys.executable,str(Path(__file__).with_name('fixture_worker.py'))])
app.run(host='127.0.0.1',port=8080,threaded=True)
