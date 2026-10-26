"""Paid phase/worker entry points cannot consume an underfunded or absent claim."""
import json
import sys

import pytest

from copilot import acceptance, acceptance_worker, agent, candidate_identity
from copilot.acceptance_io import write_json, sha256
from test_development_execution import campaign, fixtures


@pytest.mark.parametrize('phase,count,ceiling', [('pilot',24,2.4),('confirmation',12,1.2),('proposal',128,12.8)])
def test_budget_floor_is_checked_before_identity_or_claim(tmp_path,monkeypatch,phase,count,ceiling):
    _,root,docs=campaign(tmp_path)
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:pytest.fail('Underfunded identity verification'))
    plan={'mode':'proposal','phase':phase,'inputs':[{}]*count}
    for usd in (.2, (count*acceptance.CASE_MAX_NANODOLLARS-1)/1e9):
        with pytest.raises(ValueError,match='fund'):
            acceptance.authorize_run(plan,{'low':'unused','medium':'unused'},docs,root,'low',usd)
    assert not (root/(phase+'.claim.json')).exists()


def test_underfunded_pilot_leaves_no_output_or_claim(tmp_path,monkeypatch):
    reg,plan=fixtures(tmp_path);_,root,docs=campaign(tmp_path,sha256(reg))
    (docs/'protocol/batch5c-development-registry.json').write_bytes(reg.read_bytes())
    identity=tmp_path/'identity.json';write_json(identity,{})
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    monkeypatch.setattr(acceptance,'run_worker',lambda *a,**k:pytest.fail('Underfunded worker launched'))
    with pytest.raises(ValueError,match='fund'):
        acceptance.execute_plan(plan,tmp_path/'output',usd=.2,candidate=identity,candidate_medium=identity,
                                campaign_dir=root,protocol_dir=docs)
    assert not (tmp_path/'output').exists() and not (root/'pilot.claim.json').exists()


def test_paid_worker_cli_without_campaign_never_reaches_agent(tmp_path,monkeypatch):
    source=tmp_path/'input';source.write_bytes(b'invented')
    called=[]
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    monkeypatch.setattr(agent,'run_structured',lambda *a,**k:called.append(True) or {'status':'complete'})
    monkeypatch.setattr(sys,'argv',['worker','--input',str(source),'--progress',str(tmp_path/'progress'),
        '--result',str(tmp_path/'result'),'--candidate','invented','--protocol-dir','invented','--budget-usd','.1'])
    with pytest.raises(SystemExit) as exc:acceptance_worker.main()
    assert exc.value.code==2 and not called


@pytest.mark.parametrize('change',['none','identity','result','input','audit','effort','closed'])
def test_worker_claim_binds_identity_row_paths_and_single_attempt(tmp_path,change):
    from types import SimpleNamespace
    from copilot.budget import CASE_MAX_USD
    c,root,docs=campaign(tmp_path)
    output=tmp_path/'run';(output/'inputs').mkdir(parents=True);(output/'traces').mkdir()
    identity=tmp_path/'identity';identity.write_text('installed fixture')
    alias='a'*24;digest='c'*64
    c.claim(root,docs,'pilot',output,{'low':sha256(identity)})
    write_json(output/'manifest.json',{'phase':'pilot','effort':'low','variant_identities':{'low':sha256(identity)},
        'input_identities':[{'alias':alias,'effort':'low','input_sha256':digest}]})
    args=SimpleNamespace(campaign_dir=root,protocol_dir=docs,phase='pilot',alias=alias,candidate=identity,
        effort='low',input=output/'inputs'/(alias+'.npz'),progress=output/'traces'/(alias+'.progress.json'),
        result=output/'traces'/(alias+'.result.json'),audit_path=root/'paid-calls.jsonl',expected_sha256=digest,
        budget_usd=CASE_MAX_USD,deadline_monotonic=123.)
    if change=='none':
        c.authorize_worker(args)
        with pytest.raises(FileExistsError):c.authorize_worker(args)
    else:
        if change=='identity':identity.write_text('changed')
        elif change=='closed':write_json(root/'pilot.close.json',{'certified':True})
        elif change=='effort':args.effort='medium'
        elif change=='audit':args.audit_path=tmp_path/'elsewhere'
        else:setattr(args,change,tmp_path/'elsewhere')
        with pytest.raises(ValueError):c.authorize_worker(args)
        assert not (root/('pilot.'+alias+'.worker.json')).exists()
