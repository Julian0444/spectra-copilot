"""All execution entry points share limits; aggregation never rounds money."""
import json
import sys

import pytest

from copilot import acceptance, acceptance_worker, agent
from copilot.acceptance_io import sha256, write_json
from copilot.budget import Budget, Limits


def test_aggregate_exact_fractional_microdollars_and_inflight_is_uncertified():
    budget=Budget(limits=Limits(usd=.1))
    ticket=budget.reserve(1,1);budget.settle(ticket,{'input_tokens':1,'output_tokens':1})
    rows=[{'status':'complete','attempts':1,'latency_seconds':1.,'result':{'execution_budget':budget.snapshot()}} for _ in range(128)]
    result=acceptance.summarize(rows)
    assert result['cost']['known_usd']==.0000768
    assert result['cost']['known_nanodollars']==76800
    budget.reserve(1,1)
    rows[0]['result']['execution_budget']=budget.snapshot()
    assert acceptance.summarize(rows)['cost']['certified'] is False
    assert acceptance.summarize(rows)['cost']['total_usd'] is None


def test_all_128_invented_cases_receive_new_worker_budget_without_float_drift(tmp_path,monkeypatch):
    from copilot import candidate_identity
    source=tmp_path/'invented-input';source.write_text('fixture')
    identity=tmp_path/'invented-identity.json';identity.write_text('{}')
    plan=tmp_path/'plan.json'
    write_json(plan,{'schema':acceptance.SCHEMA,'mode':'proposal','inputs':[
        {'alias':f'{i:023x}a','input_path':str(source),'input_sha256':sha256(source)} for i in range(128)]})
    monkeypatch.setattr(candidate_identity,'verify',lambda *a:None)
    dispatched=[]
    def worker(item,directory,usd,seconds,**kwargs):
        dispatched.append(usd)
        ledger=Budget(limits=Limits(usd=usd))
        for _ in range(8):
            ticket=ledger.reserve(100000,4096)
            ledger.settle(ticket,{'input_tokens':100000,'output_tokens':4096})
        return {'status':'complete','model_z':.42,'execution_budget':ledger.snapshot()},False
    monkeypatch.setattr(acceptance,'run_worker',worker)
    result=acceptance.execute_plan(plan,tmp_path/'output',usd=12.337152,candidate=identity)
    assert dispatched==[.096384]*128
    assert result['status_counts']['complete']==128
    assert result['cost']['known_usd']==12.337152 and result['cost']['certified'] is True
    assert acceptance.CASE_MAX_USD==.096384


@pytest.mark.parametrize('entry',['agent','worker'])
def test_cli_and_worker_use_the_same_authorized_limits(tmp_path,monkeypatch,entry,capsys):
    from copilot import candidate_identity
    captured=[]
    def check_budget(*args,**kwargs):
        captured.append(kwargs['budget'].limits)
        return 'simulated' if entry=='agent' else {'status':'complete'}
    if entry=='agent':
        monkeypatch.setattr(agent,'run',check_budget)
        monkeypatch.setattr(sys,'argv',['agent','invented','--budget-usd','0.1'])
        assert agent.main()==0
    else:
        monkeypatch.setattr(agent,'run_structured',check_budget)
        monkeypatch.setattr(candidate_identity,'verify',lambda *a:None)
        monkeypatch.setattr(sys,'argv',['worker','--input','invented','--progress',str(tmp_path/'progress'),
            '--result',str(tmp_path/'result'),'--budget-usd','0.1','--candidate','invented','--protocol-dir','invented'])
        assert acceptance_worker.main()==0
    assert vars(captured[0])==dict(input_tokens=800000,output_tokens=32768,max_output_per_call=4096,
                                  calls=8,usd=.1,seconds=120.,retries=0)
