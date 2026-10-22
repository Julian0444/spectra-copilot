"""O-5B21-01: invented §13.9 probe plus insufficient-data minimum."""
from copy import deepcopy

import pytest

from copilot import explanation
from copilot.acceptance_score import mechanical


@pytest.mark.parametrize('assessment,expected',[('ambiguous','ambiguous'),('insufficient_line_evidence','insufficient_data')])
def test_scorer_rejects_report_below_recomputed_minimum(assessment,expected):
    prediction={'z_pred_map':.42,'z_confidence':.2}
    observations=[
        {'id':'obs-1','tool':'predict_redshift','arguments':{},'result':prediction},
        {'id':'obs-2','tool':'identify_spectral_lines','arguments':{'z':.42},'result':{
            'z_tested':.42,'n_matched':1,'n_expected_in_coverage':4,
            'ambiguous':assessment=='ambiguous','assessment':assessment,'candidates':[]}}]
    actual=explanation.result(prediction,observations,['obs-1'])
    assert actual['status']==expected and mechanical(actual)['faithful'] is True
    modified=deepcopy(actual);modified['status']='complete'
    assert mechanical(modified)['faithful'] is False
    assert mechanical(modified)['model_z_preserved'] is True
    if expected=='insufficient_data':
        modified['status']='ambiguous'
        assert mechanical(modified)['faithful'] is False
    cautious=deepcopy(actual);cautious['status']='insufficient_data'
    assert mechanical(cautious)['faithful'] is True
