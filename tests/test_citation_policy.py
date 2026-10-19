from copy import deepcopy
import json
import re

import pytest

from copilot import agent, explanation, rag, review
from copilot.report import SYSTEM
from test_explanatory_policy import PREDICTION


def evidence():
    return {'id':'obs-2','tool':'lookup_reference','arguments':{'query':'Halpha OII confusion'},
            'result':rag.lookup_reference_impl('Halpha OII confusion')}


def test_every_prompt_example_is_a_real_corpus_id():
    examples=re.findall(r'\[([A-Za-z][\w-]*)\]',SYSTEM)
    assert examples and all(x in rag.valid_ids() for x in examples)


def test_exact_fragment_provenance_is_rendered_without_new_attribution():
    o=evidence();r=explanation.result(PREDICTION,[o],['obs-2'])
    assert r['citations']
    for c in r['citations']:
        assert c['id'] in rag.valid_ids()
        assert c['text'] in explanation.render(r)
        assert c['fragment_sha256']==c['text_sha256']
        assert c['corpus_revision']==rag.corpus_revision()
        assert c['resource_sha256']==rag.corpus_hashes()[c['resource']]
    assert 'not independent certification' in explanation.render(r)


@pytest.mark.parametrize('reference',['made-up-reference','desi-targets-bgs'])
def test_nonexistent_or_not_retrieved_citation_rejected(reference):
    o=evidence()
    assert reference not in {x['id'] for x in o['result']['results']}
    with pytest.raises(ValueError,match='Citation'):
        explanation.result(PREDICTION,[o],['obs-2'],reference_ids=[reference])


@pytest.mark.parametrize('field,value',[('id','invented-paper'),('text','This proves z=9.'),
    ('source','fabricated authority'),('fragment_sha256','fake'),('resource_sha256','fake'),('fragment_end',0)])
def test_citation_cannot_attribute_invented_content(field,value):
    o=evidence();o['result']['results'][0][field]=value
    with pytest.raises(ValueError):explanation.result(PREDICTION,[o],['obs-2'])


def test_submit_only_selects_retrieved_ids_and_never_accepts_claim_text(monkeypatch):
    monkeypatch.setattr(agent.tools,'predict_redshift_impl',lambda path:PREDICTION)
    state=agent.RunTools('/opaque.npz');state.bootstrap()
    lookup={t.name:t for t in state.tools}['lookup_reference']
    got=json.loads(lookup.call({'query':'Halpha OII confusion'}))
    submit=state.tools[-1]
    with pytest.raises(ValueError):submit.call({'observation_ids':['obs-1',got['id']], 'reference_ids':['made-up']})
    assert state.result is None and state.finish()['model_z']==.42
    with pytest.raises((ValueError,TypeError)):
        submit.call({'observation_ids':['obs-1'], 'claim':'The literature proves model_z is wrong'})


def claims(ref='Halpha_6563'):
    return [{'id':'claim-1','text':'A claim for independent review','reference_ids':[ref] if ref else [],
             'external_scientific':True,'factual':True}]


def reviewer(name,support='unsupported',science='incorrect'):
    return {'reviewer':name,'independent':True,'judgments':{'claim-1':{
        'textual_support':support,'scientific_accuracy':science,'critical_error':False,
        'reference_support':{'Halpha_6563':support}}}}


def test_real_id_does_not_pass_semantic_support_or_scientific_accuracy():
    r=review.score_claim_review(claims(),reviewer('A'),reviewer('B'))
    assert r['rates']['id_validity']['rate']==1
    assert r['rates']['textual_support']['rate']==r['rates']['scientific_accuracy']['rate']==0
    assert r['evaluation_failures']['unsupported_claims']==1


def test_empty_missing_and_nonexistent_citations_do_not_pass():
    assert review.score_claim_review([])['semantic_status']=='pending_independent_review'
    assert review.score_claim_review([])['rates']['id_validity']['rate'] is None
    a,b=reviewer('A'),reviewer('B')
    for bundle in (a,b):bundle['judgments']['claim-1']['reference_support']={}
    assert review.score_claim_review(claims(None),a,b)['missing_required_citations']==1
    assert review.score_claim_review(claims('invented'))['evaluation_failures']['invalid_citation_ids']==1


def test_two_reviews_and_independent_adjudication_preserve_disagreement():
    a,b=reviewer('A'),reviewer('B','supported','correct')
    one=review.score_claim_review(claims(),a)
    assert one['pending_claims']==1 and one['rates']['textual_support']['rate'] is None
    pending=review.score_claim_review(claims(),a,b)
    assert pending['disagreements']==['claim-1'] and pending['pending_claims']==1
    r=review.score_claim_review(claims(),a,b,reviewer('C'))
    assert r['disagreements']==['claim-1'] and r['unsupported_claims']==1
    with pytest.raises(ValueError):review.score_claim_review(claims(),a,a)


def test_pair_support_is_not_inferred_from_id_or_another_citation():
    c=claims();c[0]['reference_ids'].append('OII_3727')
    a,b=reviewer('A','supported','correct'),reviewer('B','supported','correct')
    with pytest.raises(ValueError,match='pair'):review.score_claim_review(c,a,b)
    for bundle in (a,b):bundle['judgments']['claim-1']['reference_support']['OII_3727']='unsupported'
    r=review.score_claim_review(c,a,b)
    assert r['rates']['textual_support']=={'numerator':1,'denominator':2,'rate':.5}
