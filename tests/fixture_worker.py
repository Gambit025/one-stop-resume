"""UI test worker: real renderer, deterministic synthetic structure, no external API."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from job_worker import run


def structure(text):
    lines=[line for line in text.splitlines() if line.strip()]
    return {'name':lines[0],'contact':'','sections':[{'title':'','entries':[{'header':'','date':'','subtitle':'','details':lines[1:],'items':[]}]}]}

with patch('llm_generator.structure_resume_via_llm',side_effect=structure):
    run(Path(sys.argv[1]))
