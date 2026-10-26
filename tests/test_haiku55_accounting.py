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
    from test_development_execution import campaign
    _,campaign_dir,docs=campaign(tmp_path)
    write_json(campaign_dir/'pilot.claim.json',{})
    write_json(campaign_dir/'pilot.close.json',{'certified':True})
    source=tmp_path/'invented-input';source.write_text('fixture')
    identity=tmp_path/'invented-identity.json';identity.write_text('{}')
    plan=tmp_path/'plan.json'
    write_json(plan,{'schema':acceptance.SCHEMA,'mode':'proposal','inputs':[
        {'alias':f'{i:023x}a','input_path':str(source),'input_sha256':sha256(source)} for i in range(128)]})
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    dispatched=[]
    def worker(item,directory,usd,seconds,**kwargs):
        dispatched.append(usd)
        ledger=Budget(limits=Limits(usd=usd))
        for _ in range(8):
            ticket=ledger.reserve(100000,4096)
            ledger.settle(ticket,{'input_tokens':100000,'output_tokens':4096})
        return {'status':'complete','model_z':.42,'execution_budget':ledger.snapshot()},False
    monkeypatch.setattr(acceptance,'run_worker',worker)
    result=acceptance.execute_plan(plan,tmp_path/'output',usd=12.337152,candidate=identity,campaign_dir=campaign_dir,protocol_dir=docs)
    assert dispatched==[.096384]*128
    assert result['status_counts']['complete']==128
    assert result['cost']['known_usd']==12.337152 and result['cost']['certified'] is True
    assert acceptance.CASE_MAX_USD==.096384


def test_exact_remaining_case_budget_does_not_stop_at_float_boundary(tmp_path,monkeypatch):
    """0.125014 - 0.028630 rounds below 0.096384 in binary floating point."""
    from copilot import candidate_identity
    # Exercise the defensive loop at its historical exact boundary. Production
    # phase funding is tested separately and requires the full population cap.
    monkeypatch.setattr(acceptance,'authorize_run',lambda *a,**k:None)
    from test_development_execution import campaign
    _,campaign_dir,docs=campaign(tmp_path)
    write_json(campaign_dir/'pilot.claim.json',{})
    write_json(campaign_dir/'pilot.close.json',{'certified':True})
    source=tmp_path/'invented-input';source.write_text('fixture')
    identity=tmp_path/'invented-identity.json';identity.write_text('{}')
    plan=tmp_path/'plan.json'
    write_json(plan,{'schema':acceptance.SCHEMA,'mode':'proposal','inputs':[
        {'alias':f'{i:023x}a','input_path':str(source),'input_sha256':sha256(source)} for i in range(128)]})
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    dispatched=[]
    def worker(item,directory,usd,seconds,**kwargs):
        ledger=Budget(limits=Limits(usd=usd))
        usage=[(100000,4096)]*8 if dispatched else [(100000,4096)]*2+[(45340,0)]
        for n_in,n_out in usage:
            ticket=ledger.reserve(n_in,n_out)
            ledger.settle(ticket,{'input_tokens':n_in,'output_tokens':n_out})
        dispatched.append(ledger.snapshot()['known_nanodollars'])
        return {'status':'complete','model_z':.42,'execution_budget':ledger.snapshot()},False
    monkeypatch.setattr(acceptance,'run_worker',worker)
    result=acceptance.execute_plan(plan,tmp_path/'output',usd=.125014,candidate=identity,campaign_dir=campaign_dir,protocol_dir=docs)
    assert dispatched==[28630000,96384000]
    assert result['attempted']==2 and result['status_counts']['pending']==126
    assert result['cost']['known_nanodollars']==125014000 and result['cost']['certified']


@pytest.mark.parametrize('entry',['agent','worker'])
@pytest.mark.parametrize('effort',['low','medium'])
def test_cli_and_worker_use_the_same_authorized_limits(tmp_path,monkeypatch,entry,capsys,effort):
    from copilot import candidate_identity
    captured=[]
    def check_budget(*args,**kwargs):
        assert kwargs['budget'].effort==kwargs['effort']==effort
        captured.append(kwargs['budget'].limits)
        return 'simulated' if entry=='agent' else {'status':'complete'}
    if entry=='agent':
        monkeypatch.setattr(agent,'run',check_budget)
        monkeypatch.setattr(sys,'argv',['agent','invented','--budget-usd','0.1','--effort',effort])
        with pytest.raises(SystemExit) as exc:agent.main()
        assert exc.value.code==2 and not captured
        return
    else:
        from copilot import campaign
        monkeypatch.setattr(campaign,'authorize_worker',lambda args:None)  # budget propagation only
        monkeypatch.setattr(agent,'run_structured',check_budget)
        monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
        source=tmp_path/'scientific-input';source.write_bytes(b'invented fixture bytes; agent is replaced')
        monkeypatch.setattr(sys,'argv',['worker','--input',str(source),'--progress',str(tmp_path/'progress'),
            '--result',str(tmp_path/'result'),'--budget-usd','0.1','--candidate','invented','--protocol-dir','invented','--effort',effort])
        assert acceptance_worker.main()==0
    assert vars(captured[0])==dict(input_tokens=800000,output_tokens=32768,max_output_per_call=4096,
                                  calls=8,usd=.1,seconds=120.,retries=0)
