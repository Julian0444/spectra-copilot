"""Subprocess fixture: real acceptance worker/agent/SDK, invented model and HTTP.

This is never a production launcher. Socket access and checkpoint loading fail.
The local monetary ceiling exercises accounting only; HTTP is MockTransport.
"""
import json
import os
from pathlib import Path
import socket
import time

import anthropic
import httpx
import torch
from desi_fm.model import DESIFoundationModel, DESIFoundationModelConfig

from copilot import agent, acceptance_worker, candidate_identity


def main():
    events = Path(os.environ['SPECTRA_TEST_EVENTS'])
    scenario = os.environ.get('SPECTRA_TEST_SCENARIO', 'complete')

    def record(event):
        with events.open('a') as stream:
            stream.write(json.dumps(event) + '\n')

    def forbidden(*args, **kwargs):
        record({'network_or_model_forbidden': True})
        raise AssertionError('Offline worker fixture forbids network and weights')

    socket.create_connection = socket.getaddrinfo = forbidden
    socket.socket.connect = forbidden
    torch.load = forbidden
    model = DESIFoundationModel(DESIFoundationModelConfig(
        n_pixels=64, n_tokens=8, d_model=16, n_layers=1, n_heads=2, n_z_bins=16))
    agent.tools._model = lambda: model
    candidate_identity.verify = lambda *args: 'invented offline fixture identity'

    def predict(path):
        record({'predict': True})
        if scenario == 'bootstrap_failure':
            raise RuntimeError('Invented unavailable model')
        return {'z_pred_map': .42, 'z_pred': .45, 'z_confidence': .7,
                'coverage': {'contract': 'spectra-input-v3'},
                'model_identity': {'predictor': 'invented fixture'}}

    agent.tools.predict_redshift_impl = predict
    if scenario == 'prompt_tier_exceeded':
        # Inflate only invented prompt text. The worker, Budget, SDK guard and
        # run_structured are the production implementations, not substitutes.
        agent.system_prompt = lambda _: 'x' * 100001
    constructor = anthropic.Anthropic
    requests = []

    def reply(request):
        requests.append(json.loads(request.content))
        record({'mock_post': len(requests)})
        if scenario == 'inflight':
            time.sleep(30)
        if scenario == 'unknown':
            return httpx.Response(500, json={'type': 'error', 'error': {
                'type': 'api_error', 'message': 'invented failure'}})
        return httpx.Response(200, json={
            'id': 'invented', 'type': 'message', 'role': 'assistant',
            'model': requests[-1]['model'], 'content': [{
                'type': 'tool_use', 'id': 'submit', 'name': 'submit_report',
                'input': {'observation_ids': ['obs-1'], 'assessment': 'descriptive'}}],
            'stop_reason': 'tool_use', 'stop_sequence': None,
            'usage': {'input_tokens': 20, 'output_tokens': 10}})

    def client(**kwargs):
        assert kwargs['max_retries'] == 0
        return constructor(api_key='invented-unused-key', base_url='https://api.anthropic.com', max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(reply)))

    agent.anthropic.Anthropic = client
    return acceptance_worker.main()


if __name__ == '__main__':
    raise SystemExit(main())
