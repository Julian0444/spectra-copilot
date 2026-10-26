"""Only the two registered pilot efforts may reach the actual SDK request."""
import pytest

from copilot import agent
from copilot.budget import Budget, BudgetStop, Limits, PINNED_MODEL, request_bound, request_configuration
from test_evals import _source
from test_haiku55_agent import install
from test_haiku55_budget import request


@pytest.mark.parametrize('effort',['low','medium'])
def test_authorized_effort_reaches_real_sdk_with_same_limits(monkeypatch,tmp_path,effort):
    sent=install(monkeypatch,[{'type':'tool_use','id':'submit','name':'submit_report',
                              'input':{'observation_ids':['obs-1']}}],'tool_use')
    budget=Budget(limits=Limits(usd=.1),effort=effort)
    result=agent.run_structured(str(_source(tmp_path)),budget=budget,effort=effort)
    assert len(sent)==1 and result['execution_budget']['effort']==effort
    assert sent[0]['output_config']=={'effort':effort}
    assert sent[0]['thinking']=={'type':'adaptive'} and sent[0]['max_tokens']==4096


def test_effort_guard_rejects_mismatch_and_unregistered_values():
    body=request()
    with pytest.raises(BudgetStop,match='unbudgeted_request_feature'):
        request_bound(body,PINNED_MODEL,effort='medium')
    body['output_config']={'effort':'medium'}
    assert request_bound(body,PINNED_MODEL,effort='medium')[1]==4096
    for effort in ['high','auto','',None]:
        with pytest.raises(ValueError):request_configuration(effort)
        with pytest.raises(ValueError):Budget(effort=effort)


def test_agent_effort_and_ledger_mismatch_stops_before_post(monkeypatch,tmp_path):
    sent=install(monkeypatch,[],'end_turn')
    result=agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1),effort='low'),effort='medium')
    assert sent==[] and result['completion_code']=='effort_budget_mismatch'
    assert result['execution_budget']['calls']==0
