"""Invented sealed runs only. Never opens the real private acceptance manifest."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from copilot import acceptance as execute
from copilot import acceptance_score as scoring
from copilot import explanation
from copilot.acceptance_io import sha256,write_json,sanitize
from test_explanatory_policy import PREDICTION


def report(status='complete'):
    observation={'id':'obs-1','tool':'predict_redshift','arguments':{'npz_path':'spectrum.npz'},'result':PREDICTION}
    r=explanation.result(PREDICTION,[observation],['obs-1'],status=status)
    r['execution_budget']={'calls':1,'usd':.00002,'known_usd':.00002,'reserved_usd':0.,'cost_certified':True}
    return r


def plan(tmp_path,n=3):
    inputs=[];labels=[]
    for i in range(n):
        p=tmp_path/f'input{i}.npz';p.write_bytes(b'invented input bytes; injected runner only')
        alias=f'{i:023x}a'
        inputs.append({'alias':alias,'input_path':str(p),'input_sha256':sha256(p)})
        labels.append({'alias':alias,'kind':'synthetic','family':'noise','cnn_exposure':'none_synthetic',
                       'expected_answer':{'model_z_rule':'equal_to_predict_tool_if_available','must_abstain_unique_z':True,'must_reject_input':False}})
    input_path=tmp_path/'input-plan.json';label_path=tmp_path/'labels-private.json'
    write_json(input_path,{'schema':execute.SCHEMA,'mode':'simulation','inputs':inputs})
    write_json(label_path,{'schema':'batch5c-scoring-v1','cases':labels})
    return input_path,label_path,inputs


def test_labels_open_only_after_all_outputs_persisted_and_sealed(tmp_path,monkeypatch):
    p,labels,items=plan(tmp_path);out=tmp_path/'run';calls=[]
    original=Path.read_bytes
    def protected(path):
        if path==labels:
            assert (out/'seal.json').exists()
            rows=json.loads((out/'outputs.json').read_text());assert len(rows)==3
            assert all(r['attempts']==1 for r in rows)
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',protected)
    def runner(path):
        calls.append(path)
        assert path in {x['input_path'] for x in items}
        assert not (out/'seal.json').exists()
        return report('ambiguous')
    execute.execute_plan(p,out,runner=runner)
    scored=scoring.score_sealed(out,labels)
    assert len(calls)==3 and scored['global']['completion']['passed']==3
    assert scored['global']['model_z']['passed']==3 and scored['global']['abstention']['passed']==3
    assert scored['global']['semantic_review_pending_cases']==3
    assert scored['global']['semantic_metrics']['scientific_accuracy']['rate'] is None
    assert scored['labels_loaded_ns']>=scored['outputs_sealed_ns']


def test_missing_seal_or_tamper_fails_before_label_read(tmp_path,monkeypatch):
    p,labels,_=plan(tmp_path);out=tmp_path/'run';out.mkdir()
    def forbidden(path):
        if path==labels:raise AssertionError('Labels read too early')
        return original(path)
    original=Path.read_bytes;monkeypatch.setattr(Path,'read_bytes',forbidden)
    with pytest.raises(FileNotFoundError):scoring.score_sealed(out,labels)
    out.rmdir();execute.execute_plan(p,out,runner=lambda _:report())
    (out/'outputs.json').write_text('[]')
    with pytest.raises(ValueError,match='Sealed output changed'):scoring.score_sealed(out,labels)


def test_plan_rejects_labels_duplicates_and_shrunken_proposal(tmp_path):
    p,_,_=plan(tmp_path);value=json.loads(p.read_text())
    value['inputs'][0]['z_true']=.7;write_json(p,value)
    with pytest.raises(ValueError,match='labels'):execute.read_input_plan(p)
    value['inputs'][0].pop('z_true');value['inputs'][1]['alias']=value['inputs'][0]['alias'];write_json(p,value)
    with pytest.raises(ValueError,match='Duplicate'):execute.read_input_plan(p)
    value['mode']='proposal';write_json(p,value)
    with pytest.raises(ValueError,match='128'):execute.read_input_plan(p)


def test_interruption_keeps_all_cases_and_never_retries(tmp_path):
    p,labels,_=plan(tmp_path);calls=[]
    def runner(path):
        calls.append(path)
        if len(calls)==2:raise KeyboardInterrupt
        return report('ambiguous')
    out=tmp_path/'run';execute.execute_plan(p,out,runner=runner)
    rows=json.loads((out/'outputs.json').read_text())
    assert [r['status'] for r in rows]==['ambiguous','technical_error','pending']
    assert [r['attempts'] for r in rows]==[1,1,0]
    assert (out/'seal.json').exists()
    scores=scoring.score_sealed(out,labels)
    assert scores['global']['completion']['total']==3 and scores['global']['completion']['passed']==1
    with pytest.raises(FileExistsError):execute.execute_plan(p,out,runner=runner)
    assert len(calls)==2


def test_unknown_cost_stops_remaining_cases_without_dropping_them(tmp_path):
    p,_,_=plan(tmp_path);calls=[]
    def runner(path):
        calls.append(path);r=report();r['execution_budget'].update(cost_certified=False,usd=None)
        return r
    out=tmp_path/'run';s=execute.execute_plan(p,out,runner=runner)
    assert len(calls)==1 and s['status_counts']['pending']==2
    assert s['cost']['total_usd'] is None


def test_wall_timeout_retains_prediction_and_unknown_inflight_reservation(tmp_path):
    _,_,items=plan(tmp_path,1);item=items[0]
    progress={'report':report(),'execution_budget':{'calls':1,'known_usd':0,'usd':0,'reserved_usd':.01,'cost_certified':True}}
    write_json(tmp_path/(item['alias']+'.progress.json'),progress)
    result,timed_out=execute.run_worker(item,tmp_path,.1,seconds=.05,command=[sys.executable,'-c','import time;time.sleep(2)'])
    assert timed_out and result['model_z']==.42 and result['status']=='explanation_incomplete'
    assert result['execution_budget']['usd'] is None and result['completion_code']=='case_timeout'


def test_incompatible_text_redshift_or_citation_fails_mechanical_fidelity():
    r=report();assert scoring.mechanical(r)['faithful']
    wrong=deepcopy(r);wrong['model_z']=9;assert not scoring.mechanical(wrong)['model_z_preserved']
    wrong=deepcopy(r);wrong['prediction']['z_pred_map']=9
    wrong['explanation'][0]['text']='The official predictor returned model_z=9.'
    assert not scoring.mechanical(wrong)['faithful']
    wrong=deepcopy(r);wrong['citations']=[{'id':'made-up-paper'}]
    assert scoring.mechanical(wrong)['valid_citation_mentions']==0 and not scoring.mechanical(wrong)['faithful']


def test_invalid_input_and_absent_prediction_not_fabricated(tmp_path):
    import numpy as np
    p,labels,items=plan(tmp_path,1);l=json.loads(labels.read_text());l['cases'][0]['expected_answer']['must_reject_input']=True;write_json(labels,l)
    path=Path(items[0]['input_path'])
    np.savez(path,flux=np.ones(16),wavelength=np.linspace(3600,9800,16),ivar=np.zeros(16))
    value=json.loads(p.read_text());value['inputs'][0]['input_sha256']=sha256(path);write_json(p,value)
    out=tmp_path/'run';execute.execute_plan(p,out)
    score=scoring.score_sealed(out,labels)
    assert score['global']['completion']['passed']==1 and score['global']['model_z']['total']==0
    assert score['global']['model_z']['rate'] is None


def test_traces_redact_secrets_and_local_paths_but_keep_measurements_and_urls():
    raw={'api_key':'sk-ant-secret123456','history':['authorization=BearerSecret','/Users/private/folder/spectrum.npz','sk-ant-test0123456789'],
         'model_z':.42,'source':'https://example.org/paper'}
    clean=sanitize(raw);text=json.dumps(clean)
    assert 'BearerSecret' not in text and '/Users/' not in text and 'sk-ant-' not in text
    assert clean['model_z']==.42 and clean['source']==raw['source']


def test_injected_recipe_arithmetic_is_separate_from_observed_peak_recovery(tmp_path):
    p,labels,_=plan(tmp_path,1);l=json.loads(labels.read_text());c=l['cases'][0]
    c['family']='single_line';c['recipe']={'peak_angstrom':8000.,'snr':0}
    c['expected_answer']['admissible_z']=[8000/rest-1 for rest in (1215.7,3727.1,5006.8,6562.8)]
    write_json(labels,l)
    out=tmp_path/'run';execute.execute_plan(p,out,runner=lambda _:report('insufficient_data'))
    result=scoring.score_sealed(out,labels)
    assert result['rows'][0]['recipe_arithmetic_integrity'] is True
    assert result['global']['abstention']['passed']==1
    assert result['rows'][0]['checks']['model_z_preserved']
