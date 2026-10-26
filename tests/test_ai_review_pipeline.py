"""Invented end-to-end review artifacts; no real acceptance or remote calls."""
from copy import deepcopy
import json
import pytest

from copilot import review
from copilot.acceptance_io import write_json,sha256
from test_ai_review import fixture


def test_inventory_can_be_replaced_by_explicit_bound_human_resolution():
    claims,a,b=fixture();a['inventory_complete']=False
    a['inventory_disputes']=[{'kind':'exclude','claim_ids':['c1'],'reason':'Not an assertion','spans':[],'proposed_texts':[]}]
    from copilot.review_annotations import inventory_digest
    j={'reviewer':'Julian','independent':True,'judgments':{},'case_obligations':{},
       'inventory_resolution':{'input_sha256':inventory_digest(claims,a,b),'claims':[],'reason':'Exclude disputed seed'}}
    originals=deepcopy((a,b))
    scored=review.score_annotation_pair(claims,a,b,j)
    assert scored['semantic_status']=='reviewed' and scored['claims']==0
    assert scored['inventory_counts']['initial']==1 and scored['inventory_counts']['final']==0
    assert (a,b)==originals
    j['inventory_resolution']['input_sha256']='0'*64
    with pytest.raises(ValueError,match='inventory'):review.score_annotation_pair(claims,a,b,j)


def test_identity_exposure_requires_human_judgments_even_for_agreements():
    claims,a,b=fixture()
    scored=review.score_annotation_pair(claims,a,b,blindness_intact=False)
    assert scored['semantic_status']!='reviewed' and scored['pending_claims']==1
    j={**deepcopy(a),'reviewer':'Julian'}
    assert review.score_annotation_pair(claims,a,b,j,blindness_intact=False)['semantic_status']=='reviewed'
    a['identity_incident']=True
    assert review.score_annotation_pair(claims,a,b)['semantic_status']!='reviewed'


def test_human_can_reject_a_proposed_claim_but_cannot_replace_missing_annotation():
    from copilot.review_annotations import inventory_digest
    claims,a,b=fixture();a['added_claims']=[{'id':'proposed','text':'Invented omission','reference_ids':[]}]
    j={'reviewer':'Julian','independent':True,'judgments':{},'case_obligations':{},
       'inventory_resolution':{'input_sha256':inventory_digest(claims,a,b),'claims':claims,'reason':'Reject spurious proposal'}}
    assert review.score_annotation_pair(claims,a,b,j)['semantic_status']=='reviewed'
    j['inventory_resolution']['input_sha256']=inventory_digest(claims,a,None)
    assert review.score_annotation_pair(claims,a,None,j)['semantic_status']!='reviewed'


def test_validator_rejects_duplicate_added_text_and_ambiguous_obligation_shape():
    from copilot.review_annotations import validate_case,added_id
    claims,a,b=fixture();packet={'review_id':'r','claims':claims,'observations':[]}
    a.update(identity_incident=False,inventory_disputes=[])
    a['judgments']['c1']['observation_ids']=[]
    validate_case(a,packet)
    a['case_obligations']['report']={'value':'met','notes':'text'}
    with pytest.raises(ValueError,match='obligation'):validate_case(a,packet)
    a['case_obligations']['report']='met'
    a['added_claims']=[{'id':added_id('r','added'),'text':'added','reference_ids':[],'occurrences':[]},
                       {'id':'other','text':'added','reference_ids':[],'occurrences':[]}]
    with pytest.raises(ValueError,match='added'):validate_case(a,packet)


def test_packet_join_and_scoring_preserve_omissions_and_denominators(tmp_path):
    from test_acceptance import plan,report
    from copilot.acceptance import execute_plan
    from copilot.review_packet import prepare
    from copilot.review_annotations import join_annotations
    from copilot.acceptance_score import score_sealed
    p,labels,items=plan(tmp_path,1);run=tmp_path/'run';execute_plan(p,run,runner=lambda _:report())
    instructions=tmp_path/'instructions.md';instructions.write_text('Invented instructions')
    package=tmp_path/'packet';mapping=tmp_path/'mapping.json'
    manifest=prepare(run,package,mapping,instructions)
    packet=json.loads((package/'chunk-000.json').read_text())['cases'][0]
    annotations=[]
    for name in ('A','B'):
        case={'reviewer':name,'independent':True,'inventory_complete':True,'inventory_disputes':[],
              'identity_incident':False,'added_claims':[],'case_obligations':{k:'met' for k in review.OBLIGATIONS},
              'judgments':{c['id']:{'factual':True,'scientific':True,'external_scientific':False,
              'textual_support':'supported','scientific_accuracy':'incorrect','critical_error':False,
              'reference_ids':[],'reference_support':{},'observation_ids':[]} for c in packet['claims']}}
        case['case_obligations']['caution']='unmet'
        annotation=tmp_path/(name+'.json');annotations.append(annotation)
        write_json(annotation,{'schema':'batch5c-ai-annotation-v1','reviewer':name,'independent':True,
             'package_manifest_sha256':sha256(package/'manifest.json'),'cases':{packet['review_id']:case}})
    registration=tmp_path/'registration.json'
    write_json(registration,{'schema':'batch5c-annotation-registration-v1','first_sha256':sha256(annotations[0]),
                            'second_sha256':sha256(annotations[1]),'registered_before_reading_judgments':True})
    joined=tmp_path/'joined.json'
    join_annotations(package,mapping,*annotations,registration,joined)
    scored=score_sealed(run,labels,review_path=joined)
    assert scored['global']['semantic_metrics']['scientific_accuracy']['denominator']==len(packet['claims'])
    assert scored['global']['omitted_obligations']['caution']==1
    assert scored['global']['semantic_by_case']['scientific_accuracy']['total']==1
    assert scored['rows'][0]['semantic']['omitted_obligations']==['caution']
    assert manifest['seal_sha256']==json.loads(mapping.read_text())['seal_sha256']
    with pytest.raises(FileExistsError):join_annotations(package,mapping,*annotations,registration,joined)


def test_unknown_review_schema_is_rejected_and_packet_cannot_enter_seal(tmp_path):
    from test_acceptance import plan,report
    from copilot.acceptance import execute_plan
    from copilot.acceptance_score import score_sealed
    from copilot.review_packet import prepare
    p,labels,items=plan(tmp_path,1);run=tmp_path/'run';execute_plan(p,run,runner=lambda _:report())
    reviews=tmp_path/'reviews.json';write_json(reviews,{items[0]['alias']:{'schema':'batch5c-ai-annotation-v1'}})
    with pytest.raises(ValueError,match='schema'):score_sealed(run,labels,review_path=reviews)
    instructions=tmp_path/'instructions.md';instructions.write_text('invented')
    with pytest.raises(ValueError,match='sealed'):prepare(run,run/'packet',tmp_path/'map.json',instructions)
