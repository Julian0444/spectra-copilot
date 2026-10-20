"""Bounded checks for the stale surfaces identified in the 5B-2 reviews."""
import json
from pathlib import Path

from copilot import explanation
from test_eval_persistence import harness

ROOT=Path(__file__).resolve().parents[1]


def test_llm_notes_describe_descriptive_matcher_without_verdict():
    for name in ('absorption-dominated-spectra.md','desi-targets-lrg.md'):
        text=(ROOT/'copilot/refs'/name).read_text()
        assert 'weak verdict' not in text and 'weak emission-line verdict' not in text
        assert 'descriptive' in text and 'Ca H' in text
        assert 'not' in text and 'independent' in text


def test_readme_separates_current_policy_budget_and_historical_id_checks():
    text=(ROOT/'README.md').read_text()
    for obsolete in ('current agent can still propose replacements',
                     'Model-z protection and the explanatory policy are pending',
                     'current code still permits experimental agent replacements',
                     'Matcher controls and acceptance are pending in 5B',
                     'Mini-RAG with verified citations','6/6 backed'):
        assert obsolete not in text
    assert '--budget-usd 0.10' in text and '--model claude-haiku-4-5-20251001' in text
    assert 'zero by default' in text and '6/6 ID' in text
    assert 'Historical transcript' in text and 'textual support' in text


def test_evaluator_manifest_names_the_current_policy(harness):
    _,run,_,out,_=harness
    run()
    manifest=json.loads(out.with_suffix('.manifest.json').read_text())
    assert manifest['identity']['protocol']['policy']==explanation.POLICY_VERSION
