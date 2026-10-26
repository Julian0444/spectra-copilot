"""Durable call records and a fixed endpoint, using the actual guarded SDK."""
from copy import deepcopy
import json
from types import SimpleNamespace

from copilot import agent
from copilot.budget import Budget,Limits,guard_sdk
from test_haiku55_budget import request
from test_evals import _source,_install_fake_runner


def test_agent_ignores_ambient_alternate_api_endpoint(monkeypatch,tmp_path):
    _install_fake_runner(monkeypatch,submit_args={'observation_ids':['obs-1']})
    client=agent.anthropic.Anthropic();seen=[]
    monkeypatch.setenv('ANTHROPIC_BASE_URL','http://127.0.0.1:1')
    monkeypatch.setattr(agent.anthropic,'Anthropic',lambda **kwargs:(seen.append(kwargs) or client))
    agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1)))
    assert seen[0]['base_url']=='https://api.anthropic.com'


def test_post_records_response_identity_and_beta_header_before_settlement_callback():
    snapshots=[]
    def post(*a,**k):
        assert snapshots[-1]['events'][-1]['status']=='reserved'
        return SimpleNamespace(id='msg_invented',_request_id='req_invented',stop_reason='tool_use',usage={'input_tokens':20,'output_tokens':10})
    client=SimpleNamespace(max_retries=0,beta=SimpleNamespace(messages=SimpleNamespace(_post=post)))
    budget=Budget(limits=Limits(usd=.1));budget.on_change=lambda value:snapshots.append(deepcopy(value))
    with guard_sdk(client,budget):
        client.beta.messages._post('/v1/messages',body=request(),options={'headers':{'anthropic-beta':'fixture-beta'}})
    event=snapshots[-1]['events'][0]
    assert event['message_id']=='msg_invented' and event['request_id']=='req_invented'
    assert event['beta_header']=='fixture-beta' and event['response_received']
    assert event['status']=='settled' and event['stop_reason']=='tool_use'
