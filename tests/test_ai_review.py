"""Independent annotation owns classifications, inventory disputes and omissions."""
from copy import deepcopy
import pytest

from copilot import review


def fixture():
    claims=[{'id':'c1','text':'A scientific assertion','reference_ids':[],'scientific':False}]
    judgment={'factual':True,'scientific':True,'external_scientific':False,'reference_ids':[],
        'textual_support':'unsupported','scientific_accuracy':'incorrect','critical_error':False,'reference_support':{}}
    def annotation(name):
        return {'reviewer':name,'independent':True,'inventory_complete':True,
            'judgments':{'c1':{**judgment,'notes':name}},
            'case_obligations':{k:'met' for k in review.OBLIGATIONS},'added_claims':[]}
    return claims,annotation('A'),annotation('B')


def test_annotation_classification_overrides_preparer_and_ignores_notes():
    claims,a,b=fixture()
    result=review.score_annotation_pair(claims,a,b)
    assert result['scientific_claims']==1 and result['scientific_correct']==0
    assert result['semantic_status']=='reviewed' and not result['disagreements']
    claims[0]['scientific']=True
    assert review.score_annotation_pair(claims,a,b)==result


def test_classification_and_omission_disputes_stay_pending():
    claims,a,b=fixture();b['judgments']['c1']['scientific']=False
    b['case_obligations']['caution']='unmet'
    result=review.score_annotation_pair(claims,a,b)
    assert result['semantic_status']!='reviewed'
    assert 'c1' in result['disagreements'] and 'caution' in result['obligation_disagreements']
    assert result['scientific_claims']==1 and result['pending_claims']==1


def test_empty_complete_inventory_is_reviewed_but_cannot_pass_omissions():
    _,a,b=fixture()
    for annotation in (a,b):
        annotation['judgments']={};annotation['case_obligations']['report']='unmet'
    result=review.score_annotation_pair([],a,b)
    assert result['semantic_status']=='reviewed' and result['omitted_obligations']==['report']
    assert result['rates']['scientific_accuracy']['rate'] is None


def test_missing_inventory_and_added_claim_dispute_never_approve():
    claims,a,b=fixture();a['inventory_complete']=False
    assert review.score_annotation_pair(claims,a,b)['semantic_status']!='reviewed'
    a['inventory_complete']=True
    a['added_claims']=[{'id':'new','text':'Omitted statement','reference_ids':[]}]
    assert review.score_annotation_pair(claims,a,b)['semantic_status']!='reviewed'


def test_score_artifact_is_external_exclusive_and_preserves_sealed_tree(tmp_path):
    from test_acceptance import plan,report
    from copilot.acceptance import execute_plan
    from copilot.acceptance_score import score_sealed
    p,labels,_=plan(tmp_path,1);out=tmp_path/'run';execute_plan(p,out,runner=lambda _:report())
    before={x.name:x.read_bytes() for x in out.iterdir() if x.is_file()}
    target=tmp_path/'scores.json'
    score_sealed(out,labels,output_path=target)
    assert target.is_file() and before=={x.name:x.read_bytes() for x in out.iterdir() if x.is_file()}
    with pytest.raises(FileExistsError):score_sealed(out,labels,output_path=target)
    with pytest.raises(ValueError):score_sealed(out,labels,output_path=out/'scores.json')
