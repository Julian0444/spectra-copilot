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
