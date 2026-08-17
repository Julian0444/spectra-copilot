"""Offline tests for the Claude-API agent: no API key, no network calls.

The @beta_tool wrappers expose .call(dict), so the exact functions the agent
hands to the tool runner can be exercised without touching the API.
"""

import json
from pathlib import Path

from copilot import agent, tools
from copilot.report import SYSTEM

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_system_prompt_states_v21_facts():
    # The prompt must teach the agent the v2.1 output contract: z_pred_map is
    # official, confidence below ~0.3 flags outliers, the grid ceiling is 3.5.
    assert "z_pred_map" in SYSTEM
    assert "0.3" in SYSTEM
    assert "3.5" in SYSTEM
    assert "identify_spectral_lines" in SYSTEM


def test_wrapped_tool_call_matches_impl():
    # The agent-facing tool is the impl plus json.dumps — verified end to end
    # on a real held-out galaxy (z_true = 0.2036), no model involved.
    ex = str(EXAMPLES / "heldout_z020.npz")
    out = agent.identify_spectral_lines.call({"npz_path": ex, "z": 0.2036})
    r = json.loads(out)
    assert r["verdict"] == "consistent"
    assert r == tools.identify_spectral_lines_impl(ex, 0.2036)


def test_estimate_cost_usd_reproduces_rates():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert agent.estimate_cost_usd("claude-haiku-4-5", usage) == 6.0
    assert agent.estimate_cost_usd("claude-opus-4-8", usage) == 30.0
    assert agent.estimate_cost_usd("some-future-model", usage) is None


def test_estimate_cost_usd_prices_cache_tokens():
    usage = {
        "cache_creation_input_tokens": 1_000_000,  # 1.25x input rate
        "cache_read_input_tokens": 1_000_000,  # 0.1x input rate
    }
    assert agent.estimate_cost_usd("claude-haiku-4-5", usage) == 1.25 + 0.1


def test_request_kwargs_skips_thinking_on_haiku():
    # Haiku 4.5 rejects thinking={"type": "adaptive"} with a 400.
    assert agent.request_kwargs("claude-haiku-4-5") == {}
    assert agent.request_kwargs("claude-opus-4-8") == {
        "thinking": {"type": "adaptive"}
    }


def test_trap_spectrum_is_genuinely_ambiguous():
    # One emission line at 8000 A: Halpha, [OIII] 5007 and [OII] 3727 must
    # tie at exactly 1 matched line each, all weak — the agent has to report
    # the ambiguity instead of picking a winner. Lines tool only, no model.
    ex = str(EXAMPLES / "trap_single_line.npz")
    verdicts = []
    for rest in (6562.8, 5006.8, 3727.1):
        z = round(8000.0 / rest - 1.0, 4)
        r = tools.identify_spectral_lines_impl(ex, z)
        assert r["n_peaks_detected"] == 1
        assert abs(r["strongest_peaks_angstrom"][0] - 8000.0) < 2.0
        assert r["n_matched"] == 1
        verdicts.append(r["verdict"])
    assert verdicts == ["weak_or_inconsistent"] * 3
