"""The measurement's transport cannot generate messages or follow other routes."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import httpx
import pytest


def load():
    path=Path(__file__).resolve().parents[1]/'scripts/measure_batch5b22_tokens.py'
    spec=importlib.util.spec_from_file_location('count_measurement',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_only_free_count_endpoint_can_reach_transport():
    module=load();sent=[]
    transport=module.CountOnlyTransport(httpx.MockTransport(lambda req:sent.append(req.url.path) or httpx.Response(200,json={'input_tokens':1})))
    with httpx.Client(transport=transport) as client:
        for method,url in [('POST','https://api.anthropic.com/v1/messages'),
                           ('GET','https://api.anthropic.com/v1/messages/count_tokens'),
                           ('POST','https://other.invalid/v1/messages/count_tokens'),
                           ('POST','http://api.anthropic.com/v1/messages/count_tokens')]:
            with pytest.raises(RuntimeError):client.request(method,url)
        assert client.post('https://api.anthropic.com/v1/messages/count_tokens').status_code==200
    assert sent==['/v1/messages/count_tokens'] and transport.requests_made==1


def test_count_sdk_preserves_selected_configuration_and_has_no_output_limit():
    import anthropic
    from test_haiku55_budget import request
    module=load();body=request();before=deepcopy(body);sent=[]
    def reply(req):
        import json
        sent.append(json.loads(req.content));return httpx.Response(200,json={'input_tokens':30})
    with anthropic.Anthropic(api_key='invented-unused',max_retries=0,
            http_client=httpx.Client(transport=module.CountOnlyTransport(httpx.MockTransport(reply)))) as client:
        assert client.messages.count_tokens(**module.count_parameters(body)).input_tokens==30
    assert body==before
    assert sent==[{k:v for k,v in body.items() if k!='max_tokens'}]
    assert module.retry_delay('2.5')==2.5
    for invalid in (None,'nan','-1'):
        with pytest.raises(ValueError):module.retry_delay(invalid)
