"""Real SDK and invented responses: no authenticated generation or network."""
from copy import deepcopy
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from copilot import agent
from copilot.acceptance_io import sanitize
from copilot.budget import Budget, BudgetStop, Limits, guard_sdk
from test_evals import _source
from test_explanatory_policy import PREDICTION, setup_run
from test_haiku55_budget import request


def install(monkeypatch, content, reason):
    constructor=anthropic.Anthropic
    setup_run(monkeypatch)
    sent=[]
    def reply(req):
        body=json.loads(req.content);sent.append(body)
        blocks=content(len(sent)) if callable(content) else content
        return httpx.Response(200,json=dict(id='invented',type='message',role='assistant',model=body['model'],
            content=blocks,stop_reason=reason,stop_sequence=None,
            usage=dict(input_tokens=20,output_tokens=4096 if reason=='max_tokens' else 10)))
    client=constructor(api_key='invented-unused',max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    monkeypatch.setattr(agent.anthropic,'Anthropic',lambda **kwargs:client)
    return sent


@pytest.mark.parametrize('reason',['refusal','max_tokens'])
def test_terminal_model_stop_preserves_prediction_and_never_executes_tool_or_retries(monkeypatch,tmp_path,reason):
    blocks=[{'type':'thinking','thinking':'','signature':'invented-empty-thinking'},
            {'type':'tool_use','id':'never-run','name':'submit_report','input':{'observation_ids':['obs-1']}}]
    sent=install(monkeypatch,blocks,reason)
    result=agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1)))
    assert result['status']==result['completion_code']==reason
    assert result['model_z']==PREDICTION['z_pred_map'] and len(sent)==1
    assert result['execution_budget']['calls']==1 and result['execution_budget']['retries']==0
    assert result['tokens_out']==(4096 if reason=='max_tokens' else 10)
    assert result['history'][0]['content']==blocks


def test_sdk_preserves_empty_thinking_and_entire_prefix_despite_trace_sanitization(monkeypatch,tmp_path):
    thinking={'type':'thinking','thinking':'','signature':'invented-/tmp/private-signature'}
    def blocks(n):
        return [thinking, {'type':'tool_use','id':f't{n}',
            'name':'lookup_reference' if n<3 else 'submit_report',
            'input':{'query':'DESI'} if n<3 else {'observation_ids':['obs-1']}}]
    sent=install(monkeypatch,blocks,'tool_use')
    sanitized=[]
    result=agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1)),
        progress=lambda report,ledger:sanitized.append(sanitize(report)))
    assert len(sent)==3 and result['model_z']==.42
    for earlier,later in zip(sent,sent[1:]):
        assert later['system']==earlier['system'] and later['tools']==earlier['tools']
        assert later['messages'][:len(earlier['messages'])]==earlier['messages']
        assert later['messages'][-2]['content'][0]==thinking
    assert result['history'][0]['content'][0]==thinking
    assert all(body['thinking']=={'type':'adaptive'} and body['output_config']=={'effort':'low'} for body in sent)
    assert all(not set(body)&{'temperature','top_p','top_k','fallbacks'} for body in sent)


@pytest.mark.parametrize('mutation',['system','tools','earlier_message','thinking'])
def test_modified_conversation_rejected_before_post(mutation):
    sent=[]
    def post(*args,**kwargs):
        sent.append(deepcopy(kwargs['body']))
        return SimpleNamespace(usage={'input_tokens':1,'output_tokens':1})
    client=SimpleNamespace(max_retries=0,beta=SimpleNamespace(messages=SimpleNamespace(_post=post)))
    body=request();body.update(system='fixed',tools=[])
    body['messages'] += [{'role':'assistant','content':[{'type':'thinking','thinking':'','signature':'invented'}]},
                         {'role':'user','content':'Next observation'}]
    with guard_sdk(client,Budget(limits=Limits(usd=.1))):
        client.beta.messages._post('/v1/messages',body=body)
        if mutation=='system': body['system']='changed'
        elif mutation=='tools':body['tools']=[{'name':'invented','input_schema':{'type':'object'}}]
        elif mutation=='earlier_message':body['messages'][0]['content']='changed'
        else:body['messages'][1]['content'][0]['signature']='changed'
        with pytest.raises(BudgetStop,match='conversation_changed'):
            client.beta.messages._post('/v1/messages',body=body)
    assert len(sent)==1
