"""The historical 5B-2.1 replay retains its original Haiku 4.5 limits."""
import importlib.util
from pathlib import Path

from copilot.budget import Limits


def load(monkeypatch):
    root=Path(__file__).resolve().parents[1]/'scripts';monkeypatch.syspath_prepend(str(root))
    spec=importlib.util.spec_from_file_location('budget_measurement',root/'measure_batch5b21_budget.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_full_bound_replay_stops_before_fourth_request(monkeypatch):
    module=load(monkeypatch)
    requests=[{'input_bound':n,'wire_bytes':n-4096,'response_bytes':80} for n in (10000,20000,30000,40000)]
    result=module.replay(requests,'full_reserved_bound')
    assert result['admitted_calls']==3 and result['stop_reason']=='input_budget_exhausted'
    assert result['simulated_ledger']['input_tokens']==60000
    assert result['simulated_ledger']['output_tokens']==1536
    assert result['simulated_ledger']['usd']<=.1
    assert vars(module.HISTORICAL_LIMITS)==dict(input_tokens=64000,output_tokens=4096,calls=8,max_output_per_call=512,usd=0.,retries=0,seconds=120.)


def test_estimated_usage_is_separate_and_does_not_lower_the_pre_request_bound(monkeypatch):
    module=load(monkeypatch)
    oversized=[{'input_bound':65000,'wire_bytes':60904,'response_bytes':80}]
    for profile in module.PROFILES:
        result=module.replay(oversized,profile)
        assert result['admitted_calls']==0 and result['stop_reason']=='input_budget_exhausted'
