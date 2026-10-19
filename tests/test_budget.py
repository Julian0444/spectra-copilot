"""Budget decisions use fake HTTP; no external requests or credentials."""
import json
from dataclasses import replace
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from copilot import agent
from copilot.budget import Budget,Limits,BudgetStop,PINNED_MODEL,guard_sdk,request_bound
from test_evals import _install_fake_runner,_source
from test_explanatory_policy import PREDICTION


def body():
    return {'model':PINNED_MODEL,'max_tokens':512,'messages':[{'role':'user','content':'Describe evidence'}]}


def test_zero_budget_stops_before_client_construction(monkeypatch,tmp_path):
    _install_fake_runner(monkeypatch)
    monkeypatch.setattr(agent.tools,'predict_redshift_impl',lambda path:PREDICTION)
    def forbidden(**kwargs):raise AssertionError('Client must not be constructed')
    monkeypatch.setattr(agent.anthropic,'Anthropic',forbidden)
    r=agent.run_structured(str(_source(tmp_path)),budget=Budget())
    assert r['completion_code']=='paid_budget_zero' and r['model_z']==.42
    assert r['execution_budget']['calls']==0 and r['execution_budget']['usd']==0


@pytest.mark.parametrize('limits,code',[(Limits(usd=.001),'usd_budget_exhausted'),
    (Limits(usd=1,input_tokens=1),'input_budget_exhausted'),
    (Limits(usd=1,output_tokens=1),'output_budget_exhausted'),
    (Limits(usd=1,calls=0),'call_budget_exhausted'),
    (Limits(usd=1,max_output_per_call=1),'per_call_output_exceeded')])
def test_each_reservation_limit_prevents_http(limits,code):
    requests=[]
    client=anthropic.Anthropic(api_key='unused-fixture',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(lambda request:requests.append(request))))
    ledger=Budget(limits=limits)
    with guard_sdk(client,ledger),pytest.raises(BudgetStop,match=code):client.beta.messages.create(**body())
    assert requests==[] and ledger.calls==0


def test_post_boundary_stops_before_third_call_and_aggregate_limit():
    requests=[]
    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'fixture','type':'message','role':'assistant','model':PINNED_MODEL,
            'content':[],'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':5000,'output_tokens':10}})
    client=anthropic.Anthropic(api_key='unused-fixture',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    # Pad the request so actual simulated usage lies within its byte bound.
    payload=body();payload['messages'][0]['content']='x'*2000
    parent=Budget(limits=Limits(usd=.018,calls=100,input_tokens=100000))
    for _ in range(2):
        child=Budget(limits=Limits(usd=.10),parent=parent)
        with guard_sdk(client,child):client.beta.messages.create(**payload)
    child=Budget(limits=Limits(usd=.10),parent=parent)
    with guard_sdk(client,child),pytest.raises(BudgetStop,match='usd_budget'):client.beta.messages.create(**payload)
    assert len(requests)==2 and parent.snapshot()['usd']==pytest.approx(.0101)
    assert parent.spent+parent.reserved_usd<=parent.cap and child.calls==0


@pytest.mark.parametrize('usage',[None,{}, {'input_tokens':True,'output_tokens':1},
    {'input_tokens':1000000,'output_tokens':1}, {'input_tokens':1,'output_tokens':513},
    {'input_tokens':1,'output_tokens':1,'cache_creation_input_tokens':10}])
def test_unknown_or_unbudgeted_usage_locks_case_and_parent(usage):
    parent=Budget(limits=Limits(usd=1))
    child=Budget(limits=Limits(usd=.1),parent=parent)
    ticket=child.reserve(5000,512)
    with pytest.raises(BudgetStop,match='uncertified'):child.settle(ticket,usage)
    assert child.snapshot()['usd'] is None and parent.snapshot()['usd'] is None
    with pytest.raises(BudgetStop,match='uncertified'):Budget(limits=Limits(usd=.1),parent=parent).reserve(1,1)
    assert child.reserved_usd==7560


def test_http_error_never_retries_and_reservation_stays_unknown():
    requests=[]
    def reply(request):
        requests.append(request)
        return httpx.Response(500,json={'type':'error','error':{'type':'api_error','message':'simulated'}})
    client=anthropic.Anthropic(api_key='unused-fixture',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    budget=Budget(limits=Limits(usd=.1))
    with guard_sdk(client,budget),pytest.raises(anthropic.InternalServerError):client.beta.messages.create(**body())
    assert len(requests)==1 and budget.snapshot()['cost_certified'] is False
    with pytest.raises(BudgetStop):budget.reserve(1,1)


def test_single_attempt_and_no_sdk_retry_setting():
    ledger=Budget(limits=Limits(usd=.1));ledger.begin()
    with pytest.raises(BudgetStop,match='retry'):ledger.begin()
    with pytest.raises(ValueError):Budget(limits=Limits(usd=.1,retries=1))
    with pytest.raises(BudgetStop,match='sdk_retries'):
        with guard_sdk(SimpleNamespace(max_retries=2),ledger):pass


def test_text_only_bound_and_deadline(monkeypatch):
    payload=body();a=request_bound(payload,PINNED_MODEL)[0]
    payload['messages'][0]['content']='λ'*200
    assert request_bound(payload,PINNED_MODEL)[0]>a
    for key in ('thinking','cache_control','mcp_servers','context_management','output_config'):
        with pytest.raises(BudgetStop):request_bound(dict(payload,**{key:{}}),PINNED_MODEL)
    ledger=Budget(limits=Limits(usd=.1,seconds=1))
    monkeypatch.setattr('copilot.budget.time.monotonic',lambda:ledger.started+2)
    with pytest.raises(BudgetStop,match='timeout'):ledger.reserve(1,1)


def test_full_proposal_upper_cost_is_under_frozen_ceiling():
    maximum=128*(64000+4096*5)/1e6
    assert maximum==pytest.approx(10.81344) and maximum<12.80


def test_compact_tool_view_preserves_candidates_and_full_executor_evidence(tmp_path):
    from copy import deepcopy
    import numpy as np
    from copilot import tools
    wave=np.linspace(3600,9800,2048);flux=1+30*np.exp(-.5*((wave-8000)/5)**2)
    path=tmp_path/'fixture.npz';np.savez(path,flux=flux,wavelength=wave,ivar=np.ones_like(wave))
    measurement=tools.identify_spectral_lines_impl(str(path),.4)
    obs={'id':'obs-2','tool':'identify_spectral_lines','arguments':{'z':.4},'result':measurement}
    before=deepcopy(obs);wire=agent.wire_observation(obs)
    assert obs==before and len(wire['result']['candidates'])==len(measurement['candidates'])==4
    assert 'line_support' in obs['result'] and 'line_support' not in wire['result']
    for full,compact in zip(measurement['candidates'],wire['result']['candidates']):
        assert compact['z']==full['z'] and compact['measurement_id']==full['measurement_id']
        assert compact['comparison']['n_matched']==full['comparison']['n_matched']
