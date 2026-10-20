"""Exercise execute_plan -> subprocess worker -> run_structured without a fake ledger."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from copilot import acceptance, agent
from copilot.acceptance_io import sha256, write_json
from copilot.budget import Budget, Limits


def worker_plan(tmp_path, monkeypatch, *, invalid_first=False, scenario='complete'):
    items=[]
    for i in range(2):
        path=tmp_path/f'spectrum-{i}.npz'
        np.savez(path,flux=np.ones(64),wavelength=np.linspace(3600,9800,64),
                 ivar=np.zeros(64) if i==0 and invalid_first else np.ones(64))
        items.append({'alias':f'{i:023x}a','input_path':str(path),'input_sha256':sha256(path)})
    plan=tmp_path/'inputs.json'
    write_json(plan,{'schema':acceptance.SCHEMA,'mode':'simulation','inputs':items})
    events=tmp_path/'events.jsonl'
    monkeypatch.setenv('SPECTRA_TEST_EVENTS',str(events))
    monkeypatch.setenv('SPECTRA_TEST_SCENARIO',scenario)
    real_worker=acceptance.run_worker

    def offline_worker(item,directory,usd,seconds,**kwargs):
        # Only transport/model/identity are fixtures; worker, parser, ledger and
        # agent remain real. No execution_budget is constructed by this test.
        command=[sys.executable,str(Path(__file__).with_name('offline_worker.py')),
                 '--input',item['input_path'],'--progress',str(directory/(item['alias']+'.progress.json')),
                 '--result',str(directory/(item['alias']+'.result.json')),
                 '--budget-usd','0.08448','--candidate','invented.json','--protocol-dir','invented']
        return real_worker(item,directory,.08448,seconds=5 if scenario=='inflight' else 20,command=command)

    monkeypatch.setattr(acceptance,'run_worker',offline_worker)
    out=tmp_path/'run'
    summary=acceptance.execute_plan(plan,out)
    rows=json.loads((out/'outputs.json').read_text())
    calls=[json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    assert not any('network_or_model_forbidden' in event for event in calls)
    return summary,rows,calls,out


def test_invalid_then_valid_real_worker_keeps_certified_zero_and_continues(tmp_path,monkeypatch):
    summary,rows,calls,_=worker_plan(tmp_path,monkeypatch,invalid_first=True)
    assert summary['attempted']==2 and [r['attempts'] for r in rows]==[1,1]
    assert [r['status'] for r in rows]==['invalid_input','complete']
    invalid,valid=[r['result'] for r in rows]
    assert invalid['model_z'] is None
    ledger=invalid['execution_budget']
    assert ledger['cost_certified'] is True and ledger['calls']==0
    assert ledger['usd']==ledger['known_usd']==ledger['reserved_usd']==0
    assert valid['model_z']==.42 and valid['execution_budget']['calls']==1
    assert valid['execution_budget']['known_usd']==pytest.approx(.00007)
    assert summary['automatic_retries']==0 and summary['cost']['certified'] is True
    assert sum('mock_post' in event for event in calls)==1


def test_bootstrap_failure_keeps_technical_classification_and_known_zero(tmp_path,monkeypatch):
    summary,rows,calls,_=worker_plan(tmp_path,monkeypatch,scenario='bootstrap_failure')
    assert summary['attempted']==2
    assert [r['status'] for r in rows]==['technical_error','technical_error']
    assert all(r['result']['execution_budget']['cost_certified'] for r in rows)
    assert summary['cost']['total_usd']==0 and not any('mock_post' in event for event in calls)


@pytest.mark.parametrize('scenario',['unknown','inflight'])
def test_unknown_or_inflight_real_worker_stops_remaining_cases(tmp_path,monkeypatch,scenario):
    summary,rows,calls,out=worker_plan(tmp_path,monkeypatch,scenario=scenario)
    assert summary['attempted']==1 and rows[1]['status']=='pending'
    assert rows[0]['result']['model_z']==.42
    ledger=rows[0]['result']['execution_budget']
    assert ledger['cost_certified'] is False and ledger['usd'] is None
    assert ledger['reserved_usd']>0 and ledger['calls']==1
    assert json.loads((out/'summary.json').read_text())['stop_reason']=='usage_uncertified'
    assert sum('mock_post' in event for event in calls)==1 and summary['automatic_retries']==0


def test_prebootstrap_rejection_retains_accumulated_budget(tmp_path):
    ledger=Budget(limits=Limits(usd=.1))
    ticket=ledger.reserve(100,20)
    ledger.settle(ticket,{'input_tokens':40,'output_tokens':10})
    expected=ledger.snapshot()
    result=agent.run_structured(str(tmp_path/'missing.npz'),budget=ledger)
    assert result['status']=='invalid_input' and result['execution_budget']==expected


def test_unconstructed_budget_is_not_assumed_certified_zero(tmp_path):
    result=agent.run_structured(str(tmp_path/'missing.npz'),model='unpriced-invented-model')
    assert result['execution_budget'] is None
