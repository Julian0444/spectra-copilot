"""A later phase must use the registered choice and final operational evidence."""
from copy import deepcopy
import pytest


def test_next_phase_binds_choice_code_and_gate():
    from copilot.pilot_decision import check_transition
    decision={'chosen_effort':'medium','pilot_llm_path_sha256':'a'*64}
    final={'effort':'medium','llm_path_sha256':'a'*64,'gate_passed':True}
    check_transition('proposal','medium','a'*64,decision,final)
    for effort,path,gate in [('low','a'*64,True),('medium','b'*64,True),('medium','a'*64,False)]:
        with pytest.raises(ValueError):check_transition('proposal',effort,path,decision,{**final,'gate_passed':gate})
    with pytest.raises(ValueError):check_transition('confirmation','medium','a'*64,decision,final)
    with pytest.raises(ValueError):check_transition('confirmation','medium','b'*64,decision,final)
    correction={'old_llm_path_sha256':'a'*64,'new_llm_path_sha256':'b'*64,'description':'Demonstrated harness defect',
                'reproduction_sha256':'c'*64,'before_commit':'d'*40,'after_commit':'e'*40}
    check_transition('confirmation','medium','b'*64,decision,final,correction)


def test_gate_rejects_pending_invalid_valid_case_unknown_and_inflight():
    from copilot.pilot_score import aggregate,measure_row
    from test_acceptance import report
    from copilot.explanation import result
    rows=[measure_row({'alias':str(i),'status':'complete','result':report(),'attempts':1,'latency_seconds':1},{}) for i in range(11)]
    invalid=result(status='invalid_input');invalid['execution_budget']={'calls':0,'events':[],'cost_certified':True,'known_usd':0,'reserved_usd':0,'usd':0}
    rows.append(measure_row({'alias':'invalid','status':'invalid_input','result':invalid,'attempts':1,'latency_seconds':1},{'expected_answer':{'must_reject_input':True}}))
    assert aggregate(rows)['gate_passed']
    for key,value in [('status','pending'),('status','invalid_input'),('status','technical_error'),('cost_certified',False),('reserved_nanodollars',1),('prompt_tier_exceeded',True)]:
        changed=deepcopy(rows);changed[0][key]=value
        assert not aggregate(changed)['gate_passed']


def test_confirmation_uses_same_twelve_inputs_and_registered_effort(tmp_path):
    import json
    from copilot.acceptance_io import write_json,sha256
    from copilot.development import prepare_confirmation,validate_plan
    from test_development_execution import fixtures
    reg,plan=fixtures(tmp_path)
    (tmp_path/'pilot-inputs.json').write_bytes(plan.read_bytes())
    write_json(tmp_path/'development-scoring.json',{'schema':'batch5c-development-scoring-v1',
        'cases':[{'alias':i['alias'],'effort':i['effort'],'slot':n//2} for n,i in enumerate(json.loads(plan.read_text())['inputs'])]})
    decision=tmp_path/'decision.json';write_json(decision,{'chosen_effort':'medium'})
    prepare_confirmation(tmp_path,decision,tmp_path/'confirmation')
    prepared=json.loads((tmp_path/'confirmation/confirmation-inputs.json').read_text())
    assert len(validate_plan(prepared,reg,sha256(reg),'medium'))==12
    assert all(i['effort']=='medium' for i in prepared['inputs'])
