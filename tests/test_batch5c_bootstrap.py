"""5C: executor supplies both initial observations and spends two analyses."""
import json
from copy import deepcopy

import pytest

from copilot import agent
from copilot.budget import Budget, Limits
from test_explanatory_policy import PREDICTION
from test_evals import _source
from test_haiku55_agent import install


MATCH = {'z_tested':.42, 'n_matched':0, 'n_expected_in_coverage':3,
         'assessment':'insufficient_line_evidence', 'ambiguous':False,
         'measurements':[], 'candidates':[]}


def test_bootstrap_predict_then_matcher_counts_two_of_six(monkeypatch):
    called=[]
    def predict(path):
        called.append(('predict',path));return deepcopy(PREDICTION)
    def matcher(path,z):
        called.append(('matcher',path,z));return deepcopy(MATCH)
    monkeypatch.setattr(agent.tools,'predict_redshift_impl',predict)
    monkeypatch.setattr(agent.tools,'identify_spectral_lines_impl',matcher)
    state=agent.RunTools('/invented.npz');state.bootstrap()
    assert called==[('predict','/invented.npz'),('matcher','/invented.npz',.42)]
    assert state.calls==2
    assert [o['tool'] for o in state.observations]==['predict_redshift','identify_spectral_lines']
    for _ in range(4):state.tools[0].call({'npz_path':state.path})
    with pytest.raises(ValueError,match='budget'):state.tools[0].call({'npz_path':state.path})
    assert state.calls==6
    state.tools[-1].call({'observation_ids':['obs-1']})
    assert state.finish()['status']=='insufficient_data'
    assert state.finish()['observations'][1]['result']==MATCH


def test_real_sdk_initial_message_contains_both_observations_even_for_immediate_submit(monkeypatch,tmp_path):
    sent=install(monkeypatch,[{'type':'tool_use','id':'submit','name':'submit_report',
                              'input':{'observation_ids':['obs-1']}}],'tool_use')
    monkeypatch.setattr(agent.tools,'identify_spectral_lines_impl',lambda path,z:deepcopy(MATCH))
    result=agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1)))
    assert len(sent)==1 and result['status']=='insufficient_data'
    assert result['model_z']==.42 and len(result['observations'])==2
    initial=sent[0]['messages'][0]['content']
    assert '"tool": "predict_redshift"' in initial
    assert '"tool": "identify_spectral_lines"' in initial
    assert 'insufficient_line_evidence' in initial


def test_failed_initial_matcher_keeps_prediction_without_paid_request(monkeypatch,tmp_path):
    sent=install(monkeypatch,[],'end_turn')
    def failed(path,z):raise RuntimeError('invented unavailable matcher')
    monkeypatch.setattr(agent.tools,'identify_spectral_lines_impl',failed)
    result=agent.run_structured(str(_source(tmp_path)),budget=Budget(limits=Limits(usd=.1)))
    assert sent==[] and result['model_z']==.42
    assert result['observations'][1]['error']=='technical_error'
    assert result['execution_budget']['calls']==0 and result['execution_budget']['cost_certified']
