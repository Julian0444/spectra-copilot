"""Frozen operational selection never uses redshift accuracy or gate filtering."""
from copy import deepcopy
import pytest


def variant(valid,failures,cost,gate=True):
    return {'valid_reports':valid,'max_tokens_or_refusal':failures,'cost_certified':True,
            'known_nanodollars':cost,'gate_passed':gate}


def test_selection_precedes_gate_even_when_other_variant_passes():
    from copilot.pilot_score import choose
    metrics={'low':variant(10,0,100,False),'medium':variant(10,1,90,True)}
    assert choose(metrics)=='low'
    metrics['low']['valid_reports']=9;assert choose(metrics)=='medium'


def test_selection_ties_use_cost_then_low_and_reject_unknown_spend():
    from copilot.pilot_score import choose
    metrics={'low':variant(10,1,100),'medium':variant(10,1,99)}
    assert choose(metrics)=='medium'
    metrics['medium']['known_nanodollars']=100;assert choose(metrics)=='low'
    metrics['low']['cost_certified']=False
    with pytest.raises(ValueError,match='uncertified'):choose(metrics)


def test_mechanical_row_ignores_catalog_z_but_requires_abstention_and_zero_invalid_calls():
    from copilot.pilot_score import measure_row
    from test_acceptance import report
    row={'alias':'invented','status':'complete','result':report(),'attempts':1,'latency_seconds':1}
    label={'expected_answer':{'must_abstain_unique_z':True},'label':{'z':.42}}
    first=measure_row(row,label)
    assert not first['all_obligations']
    row['status']='ambiguous';row['result']=report('ambiguous')
    first=measure_row(row,label);assert first['all_obligations']
    label['label']['z']=999;label['expected_answer']['catalog_reference_z']=-50
    assert measure_row(row,label)==first
    from copilot.explanation import result
    row.update(status='invalid_input',result=result(status='invalid_input'))
    row['result']['execution_budget']={'calls':0,'events':[],'known_usd':0,'usd':0,'reserved_usd':0,'cost_certified':True}
    label={'expected_answer':{'must_reject_input':True}}
    assert measure_row(row,label)['correct_invalid']
    row['result']['execution_budget']['calls']=1
    assert not measure_row(row,label)['correct_invalid']
