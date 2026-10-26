"""The LLM's choice of cited observations cannot hide executor evidence."""
from copy import deepcopy
import json
from pathlib import Path
import re
import socket

import anthropic
import httpx
import numpy as np
import pytest

from copilot import agent, explanation, tools
from copilot.budget import Budget, Limits
from test_explanatory_policy import PREDICTION, setup_run


def observations(assessment='ambiguous'):
    return [
        {'id':'obs-1','tool':'predict_redshift','arguments':{},'result':PREDICTION},
        {'id':'obs-2','tool':'identify_spectral_lines','arguments':{'z':.42},'result':{
            'z_tested':.42,'n_matched':1,'n_expected_in_coverage':4,
            'ambiguous':assessment=='ambiguous','assessment':assessment,
            'candidates':[{'candidate_id':'a','z':2.,'measurement_id':'peak-1','assumed_line':'Lyα'},
                          {'candidate_id':'b','z':.7,'measurement_id':'peak-1','assumed_line':'[O II]'}]}}]


@pytest.mark.parametrize('selected',[['obs-1'],['obs-1','obs-2'],['obs-2']])
def test_all_registered_alternatives_and_ambiguity_survive_selection(selected):
    evidence=observations();before=deepcopy(evidence)
    result=explanation.result(PREDICTION,evidence,selected)
    assert result['status']=='ambiguous' and result['model_z']==.42
    assert [c['z'] for c in result['alternatives']]==[2.,.7]
    assert all(c['observation_id']=='obs-2' for c in result['alternatives'])
    assert evidence==before


@pytest.mark.parametrize('selected',[['obs-1'],['obs-1','obs-2']])
@pytest.mark.parametrize('assessment',['descriptive','ambiguous','insufficient_data'])
def test_insufficient_line_evidence_is_executor_minimum(selected,assessment):
    evidence=observations('insufficient_line_evidence');evidence[1]['result']['candidates']=[]
    result=explanation.result(PREDICTION,evidence,selected,assessment=assessment)
    assert result['status']=='insufficient_data' and result['model_z']==.42
    assert result['alternatives']==[]


def test_llm_can_increase_caution_and_failures_keep_their_classification():
    evidence=observations()
    cautious=explanation.result(PREDICTION,evidence,['obs-1'],assessment='insufficient_data')
    assert cautious['status']=='insufficient_data' and len(cautious['alternatives'])==2
    for status in ('technical_error','explanation_incomplete'):
        report=explanation.result(PREDICTION,evidence,['obs-1'],status=status)
        assert report['status']==status and report['model_z']==.42 and len(report['alternatives'])==2


def test_single_blue_peak_never_claims_unique_solution(tmp_path):
    wave=np.linspace(3600,9800,12401);flux=1+40*np.exp(-.5*((wave-3680)/5)**2)
    path=tmp_path/'invented-blue-line.npz';np.savez(path,flux=flux,wavelength=wave,ivar=np.ones_like(wave))
    measured=tools.identify_spectral_lines_impl(str(path),0.)
    assert measured['n_peaks_detected']==1 and len(measured['candidates'])==1
    assert measured['ambiguous'] is True and measured['assessment']=='ambiguous'
    assert measured['physical_confirmation'] is False


@pytest.mark.parametrize('selected',[['obs-1'],['obs-1','obs-2']])
def test_public_heldout_sdk_cannot_hide_ambiguity(monkeypatch,selected):
    constructor=anthropic.Anthropic
    setup_run(monkeypatch)
    def forbidden(*args,**kwargs):raise AssertionError('No network in this integration regression')
    monkeypatch.setattr(socket,'create_connection',forbidden)
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(socket,'getaddrinfo',forbidden)
    requests=[]
    def reply(request):
        body=json.loads(request.content);requests.append(body)
        path=re.search(r'Analyze the spectrum in (\S+) and',body['messages'][0]['content']).group(1)
        name='identify_spectral_lines' if len(requests)==1 else 'submit_report'
        args={'npz_path':path,'z':.42} if len(requests)==1 else {'observation_ids':selected,'assessment':'descriptive'}
        return httpx.Response(200,json={'id':f'm{len(requests)}','type':'message','role':'assistant','model':body['model'],
            'content':[{'type':'tool_use','id':f't{len(requests)}','name':name,'input':args}],
            'stop_reason':'tool_use','stop_sequence':None,'usage':{'input_tokens':20,'output_tokens':10}})
    client=constructor(api_key='invented-unused',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    monkeypatch.setattr(agent.anthropic,'Anthropic',lambda **kwargs:client)
    source=Path(__file__).resolve().parents[1]/'examples/heldout_z020.npz'
    report=agent.run_structured(str(source),budget=Budget(limits=Limits(usd=.1)))
    measurement=report['observations'][1]['result']
    assert len(requests)==2 and measurement['ambiguous'] and measurement['candidates']
    assert report['status']=='ambiguous' and report['model_z']==PREDICTION['z_pred_map']
    assert report['alternatives']==[dict(c,observation_id=o['id']) for o in report['observations']
                                    if o['tool']=='identify_spectral_lines' for c in o['result']['candidates']]
    assert report['execution_budget']['retries']==0
