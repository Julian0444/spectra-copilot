"""Offline tests for the plan-11 eval harness: no API key, no network.

run_structured is exercised against a fake tool runner injected through
anthropic.Anthropic, so the structured-output contract (submit_report payload
+ token accounting) is tested without spending a single token. The eval
scripts in eval/ are plain scripts, not a package — they are loaded by path.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from copilot import agent

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, EVAL_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeMessage:
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _install_fake_runner(monkeypatch, submit_args=None, captured=None):
    """anthropic.Anthropic -> a client whose tool_runner yields 2 fake turns
    and (optionally) simulates the model calling submit_report."""

    def tool_runner(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        if submit_args is not None:
            agent.submit_report.call(submit_args)
        return [_FakeMessage(), _FakeMessage()]

    fake = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(tool_runner=tool_runner))
    )
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda: fake)


def test_submit_report_records_typed_payload():
    agent.SUBMITTED.pop("last", None)
    out = agent.submit_report.call(
        {"z_final": "0.42", "confidence": "high", "lines_matched": "7",
         "summary": "8/11 lines matched (identify_spectral_lines)."}
    )
    assert out == "recorded"
    rec = agent.SUBMITTED["last"]
    assert rec["z_final"] == 0.42 and isinstance(rec["z_final"], float)
    assert rec["lines_matched"] == 7 and isinstance(rec["lines_matched"], int)
    assert rec["confidence"] == "high"


def test_run_structured_returns_payload_with_token_accounting(monkeypatch):
    captured = {}
    _install_fake_runner(
        monkeypatch,
        submit_args={"z_final": 1.98, "confidence": "low", "lines_matched": 2,
                     "summary": "ambiguous"},
        captured=captured,
    )
    r = agent.run_structured("some.npz", model="claude-haiku-4-5")
    assert r["z_final"] == 1.98 and r["confidence"] == "low"
    assert r["tokens_in"] == 200 and r["tokens_out"] == 40  # 2 fake turns
    assert r["usage"]["input_tokens"] == 200
    # The request must offer submit_report, teach the extra rule, and keep
    # the Haiku no-thinking contract of request_kwargs().
    names = {t.name for t in captured["tools"]}
    assert "submit_report" in names and "find_similar_spectra" in names
    assert "submit_report exactly once" in captured["system"]
    assert "thinking" not in captured


def test_run_structured_none_when_agent_never_submits(monkeypatch):
    _install_fake_runner(monkeypatch, submit_args=None)
    agent.SUBMITTED["last"] = {"z_final": 9.9}  # stale result from a prior run
    assert agent.run_structured("some.npz") is None  # stale state must not leak


def test_select_cases_is_stratified_and_deterministic():
    import csv

    export = _load_script("export_cases")
    with open(EVAL_DIR / "heldout_predictions_v21.csv") as f:
        z = [float(r["z_true"]) for r in csv.DictReader(f)]
    idx = export.select_cases(z, n=150, seed=7)
    assert len(idx) == 150 and len(set(idx)) == 150
    assert idx == sorted(idx)
    assert all(0 <= i < len(z) for i in idx)
    # The failure band the eval exists to measure must be oversampled.
    assert sum(z[i] > 1.5 for i in idx) >= 20
    assert idx == export.select_cases(z, n=150, seed=7)


def test_summarize_reports_both_systems_and_confidence_correlation():
    run_evals = _load_script("run_evals")
    rows = [
        # agent right, model right, high confidence
        {"case": "a", "z_true": "0.5", "z_model": "0.51", "z_final": "0.5",
         "confidence": "high", "dzn": "0.0", "ok15": "1", "ok05": "1",
         "tokens": "1000", "status": "ok"},
        # agent right where the model was catastrophic (the recovery story)
        {"case": "b", "z_true": "1.6", "z_model": "0.9", "z_final": "1.58",
         "confidence": "medium", "dzn": "0.0077", "ok15": "1", "ok05": "1",
         "tokens": "2000", "status": "ok"},
        # agent wrong, low confidence — honesty preserved in by_confidence
        {"case": "c", "z_true": "2.0", "z_model": "1.0", "z_final": "1.0",
         "confidence": "low", "dzn": "0.3333", "ok15": "0", "ok05": "0",
         "tokens": "3000", "status": "ok"},
        # agent errored: still counts in the model-only baseline
        {"case": "d", "z_true": "0.2", "z_model": "0.21", "z_final": "",
         "confidence": "", "dzn": "", "ok15": "", "ok05": "",
         "tokens": "", "status": "error"},
    ]
    s = run_evals.summarize(rows)
    assert s["n"] == 4 and s["n_ok"] == 3 and s["n_error"] == 1
    assert s["model_only"]["n"] == 4
    assert s["model_only"]["rate_015"] == 0.5  # a, d fine; b, c catastrophic
    assert s["agent"]["rate_015"] == round(2 / 3, 3)
    assert s["agent"]["by_confidence"]["high"] == {"n": 1, "rate_015": 1.0}
    assert s["agent"]["by_confidence"]["low"] == {"n": 1, "rate_015": 0.0}
    assert s["agent"]["total_tokens"] == 6000


def test_dz_norm_matches_convention():
    run_evals = _load_script("run_evals")
    assert abs(run_evals.dz_norm(1.15, 1.0) - 0.075) < 1e-12  # |dz| / (1 + z_true)
    assert abs(run_evals.dz_norm(0.85, 1.0) - 0.075) < 1e-12
