"""5B-2.2 price/configuration gates, using invented text and exact worked costs."""
from copy import deepcopy
from decimal import Decimal

import pytest

from copilot import agent
from copilot.budget import Budget, BudgetStop, Limits, PINNED_MODEL, request_bound


def request():
    return dict(model='claude-haiku-5-5', max_tokens=4096,
                thinking={'type':'adaptive'}, output_config={'effort':'low'},
                messages=[{'role':'user','content':'Invented spectrum evidence'}])


def test_fixed_model_explicit_settings_and_official_two_tier_prices():
    assert PINNED_MODEL == 'claude-haiku-5-5'
    assert agent.request_kwargs(PINNED_MODEL) == {'thinking':{'type':'adaptive'}, 'output_config':{'effort':'low'}}
    assert agent.estimate_cost_usd(PINNED_MODEL, {'input_tokens':100000, 'output_tokens':4096}) == .012048
    assert agent.estimate_cost_usd(PINNED_MODEL, {'input_tokens':100001, 'output_tokens':4096}) == .0602405
    assert agent.estimate_cost_usd('claude-haiku-4-5-20251001', {'input_tokens':1000000, 'output_tokens':1000000}) == 6.


def test_authorized_limits_cover_eight_full_reservations_with_exact_cost():
    limits = Limits(usd=.10)
    assert vars(limits) == dict(input_tokens=800000, output_tokens=32768, calls=8,
                              max_output_per_call=4096, usd=.10, retries=0, seconds=120.)
    ledger = Budget(limits=limits)
    for _ in range(8):
        ticket = ledger.reserve(100000, 4096)
        ledger.settle(ticket, {'input_tokens':100000, 'output_tokens':4096})
    assert ledger.snapshot()['usd'] == .096384
    assert Decimal(str(ledger.snapshot()['usd'])) * 128 == Decimal('12.337152')
    with pytest.raises(BudgetStop, match='call_budget_exhausted'):
        ledger.reserve(1, 1)


def test_sub_microdollar_reservation_and_settlement_are_exact():
    parent = Budget(limits=Limits(usd=.000002))
    child = Budget(limits=Limits(usd=.0000012), parent=parent)
    for _ in range(2):
        ticket = child.reserve(1, 1)
        assert child.snapshot()['reserved_usd'] == .0000006
        child.settle(ticket, {'input_tokens':1, 'output_tokens':1})
    assert child.snapshot()['usd'] == parent.snapshot()['usd'] == .0000012
    assert child.snapshot()['known_nanodollars'] == 1200
    with pytest.raises(BudgetStop, match='usd_budget_exhausted'):
        child.reserve(1, 0)


def test_new_request_keeps_conservative_utf8_bound_without_mutation():
    import json
    body = request(); body['messages'][0]['content'] = 'λ' * 37
    before = deepcopy(body)
    expected = len(json.dumps(body, ensure_ascii=False, separators=(',',':')).encode()) + 4096
    assert request_bound(body, PINNED_MODEL) == (expected, 4096)
    assert body == before


@pytest.mark.parametrize('field,value', [
    ('thinking', {'type':'disabled'}), ('thinking', {'type':'adaptive','display':'summarized'}),
    ('output_config', {'effort':'high'}), ('output_config', {'effort':'low','format':{'type':'json_schema'}}),
    ('temperature',0), ('top_p',1), ('top_k',1), ('fallbacks',[]),
    ('stream',False), ('cache_control',{}), ('mcp_servers',[]), ('context_management',{}),
])
def test_unapproved_request_settings_rejected(field, value):
    body = request(); body[field] = value
    with pytest.raises(BudgetStop, match='unbudgeted_request_feature'):
        request_bound(body, 'claude-haiku-5-5')


def test_missing_configuration_prefill_and_server_tools_rejected():
    body = request(); del body['thinking']
    with pytest.raises(BudgetStop): request_bound(body, 'claude-haiku-5-5')
    body = request(); body['messages'][-1]['role'] = 'assistant'
    with pytest.raises(BudgetStop, match='prefill'): request_bound(body, 'claude-haiku-5-5')
    body = request(); body['tools'] = [{'type':'web_search_20250305','name':'web_search'}]
    with pytest.raises(BudgetStop): request_bound(body, 'claude-haiku-5-5')


def test_prompt_bound_at_threshold_is_allowed_and_above_is_rejected():
    body = request(); body['messages'][0]['content'] = ''
    overhead = request_bound(body, 'claude-haiku-5-5')[0]
    body['messages'][0]['content'] = 'x' * (100000-overhead)
    assert request_bound(body, 'claude-haiku-5-5')[0] == 100000
    body['messages'][0]['content'] += 'x'
    with pytest.raises(BudgetStop, match='prompt_tier_exceeded'):
        request_bound(body, 'claude-haiku-5-5')
    with pytest.raises(BudgetStop, match='prompt_tier_exceeded'):
        Budget(limits=Limits(usd=.1)).reserve(100001,1)
