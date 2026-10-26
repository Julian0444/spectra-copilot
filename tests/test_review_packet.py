"""Review views preserve published science and hide LLM execution metadata."""
import json
from copy import deepcopy

from copilot import explanation
from test_acceptance import report


def test_packet_deduplicates_model_z_and_preserves_predictor_numbers():
    from copilot.review_packet import case_packet
    r=report();r['prediction']['model_identity']={'configured_range':[0,6],'checkpoint':{'step':30000,'sha256':'a'*64}}
    r['predictor']=deepcopy(r['prediction']['model_identity'])
    r['execution_budget']['model']='claude-haiku-5-5';r['history']=[{'thinking':'hidden','model':'claude-haiku-5-5'}]
    row={'alias':'f'*24,'status':'complete','result':r}
    packet=case_packet(row,'a'*64)
    z=[c for c in packet['claims'] if c['equivalence_key']=='official_model_z']
    assert len(z)==1 and len(z[0]['occurrences'])==2
    assert packet['report']['predictor']['configured_range']==[0,6]
    assert packet['report']['predictor']['checkpoint']['step']==30000
    text=json.dumps(packet)
    assert 'claude-haiku' not in text and 'execution_budget' not in text and row['alias'] not in text
    assert len([c for c in packet['claims'] if c['equivalence_key'].startswith('lim:')])==3
    assert packet==case_packet(row,'a'*64)


def test_packet_marks_identity_exposure_without_editing_scientific_text():
    from copilot.review_packet import case_packet
    r=report();r['observations'][0]['arguments']['query']='Claude gave this hypothesis'
    packet=case_packet({'alias':'a'*24,'status':'complete','result':r},'b'*64)
    assert not packet['blindness_intact']
    assert packet['observations'][0]['arguments']['query']=='Claude gave this hypothesis'


def test_no_result_has_no_invented_report_or_claims():
    from copilot.review_packet import case_packet
    packet=case_packet({'alias':'a'*24,'status':'pending','result':None},'b'*64)
    assert packet['report'] is None and packet['claims']==[] and not packet['published_report']


def test_matcher_qualifiers_are_atomic_and_grouped_across_template_spans():
    from copilot.review_packet import case_packet
    r=report()
    observation={'id':'obs2','tool':'identify_spectral_lines','arguments':{},
                 'result':{'z_tested':.3,'n_matched':2,'n_expected_in_coverage':4}}
    r['observations'].append(observation)
    r['explanation'].append({'observation_id':'obs2','text':
        'At hypothesis z=0.3, the matcher counted 2 matches among 4 line positions in coverage. '
        'These are descriptive measurements, not physical confirmation.'})
    packet=case_packet({'alias':'f'*24,'status':'complete','result':r},'a'*64)
    by_key={c['equivalence_key']:c for c in packet['claims']}
    assert len(by_key['matcher_descriptive']['occurrences'])==2
    assert len(by_key['absence_not_refutation']['occurrences'])==1
    assert len(by_key['matcher_not_confirmation']['occurrences'])==1
    for claim in packet['claims']:
        for occurrence in claim['occurrences']:
            import hashlib
            assert occurrence['text_sha256']==hashlib.sha256(occurrence['text'].encode()).hexdigest()
