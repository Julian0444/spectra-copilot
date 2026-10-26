"""Regression probes for input bytes and the parent's absolute deadline."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import time

import numpy as np
import pytest

from copilot import agent, acceptance_worker, candidate_identity
from copilot.budget import BudgetStop


def spectrum():
    stream=BytesIO()
    np.savez(stream,flux=np.ones(64),wavelength=np.linspace(3600,9800,64),ivar=np.ones(64))
    return stream.getvalue()


def test_agent_parses_and_hashes_one_read_even_when_source_changes(tmp_path,monkeypatch):
    path=tmp_path/'input.npz';payload=spectrum();path.write_bytes(payload)
    original=agent.read_npz
    def racing_read(source):
        batch=original(source)
        path.write_bytes(b'replaced after parse')
        return batch
    monkeypatch.setattr(agent,'read_npz',racing_read)
    monkeypatch.setattr(agent.tools,'_model',lambda:None)
    monkeypatch.setattr(agent,'_prepare_inputs',lambda *a:None)
    with agent.agent_input(path) as (_,provenance):
        assert provenance['source_sha256']==hashlib.sha256(payload).hexdigest()


def test_worker_rejects_changed_bytes_with_certified_zero(tmp_path,monkeypatch):
    path=tmp_path/'input.npz';path.write_bytes(spectrum())
    result=tmp_path/'result.json';progress=tmp_path/'progress.json'
    monkeypatch.setattr(sys,'argv',['worker','--input',str(path),'--result',str(result),
        '--progress',str(progress),'--expected-sha256','0'*64])
    monkeypatch.setattr(agent,'run_structured',lambda *a,**k:pytest.fail('Changed bytes reached agent'))
    assert acceptance_worker.main()==0
    report=json.loads(result.read_text())
    assert report['completion_code']=='input_identity_mismatch'
    assert report['execution_budget']['cost_certified']
    assert report['execution_budget']['calls']==0


def test_identity_time_counts_inside_parent_deadline(tmp_path,monkeypatch):
    path=tmp_path/'input.npz';path.write_bytes(spectrum())
    result=tmp_path/'result.json';progress=tmp_path/'progress.json'
    monkeypatch.setattr(sys,'argv',['worker','--input',str(path),'--result',str(result),
        '--progress',str(progress),'--budget-usd','.1','--candidate','fixture.json',
        '--protocol-dir','fixture','--deadline-monotonic',str(time.monotonic()-.01)])
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    monkeypatch.setattr(agent,'run_structured',lambda *a,**k:pytest.fail('Expired deadline reached agent'))
    assert acceptance_worker.main()==0
    report=json.loads(result.read_text())
    assert report['completion_code']=='case_timeout'
    assert report['execution_budget']['cost_certified'] and report['execution_budget']['calls']==0
