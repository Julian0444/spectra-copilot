"""Offline tests for the MCP server: no checkpoint, no network, no client LLM.

They exercise the real MCP layer (list_tools / call_tool on the MCPServer
instance) so a schema or delegation regression fails here, not inside
Claude Code.
"""

import asyncio
import json
from pathlib import Path

from copilot import tools
from copilot.mcp_server import mcp

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _run(coro):
    return asyncio.run(coro)


def _payload(result):
    """JSON dict from a CallToolResult's text content."""
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def test_exposes_exactly_the_three_tools():
    ts = _run(mcp.list_tools())
    assert {t.name for t in ts} == {
        "predict_redshift", "identify_spectral_lines", "reconstruct_spectrum"
    }


def test_descriptions_say_when_to_use_and_schemas_match():
    ts = {t.name: t for t in _run(mcp.list_tools())}
    # The description is all an MCP client sees to decide when to call a
    # tool: it must state the *when*, not just the what.
    assert "Use this first" in ts["predict_redshift"].description
    assert "z_confidence" in ts["predict_redshift"].description
    d = ts["identify_spectral_lines"].description
    assert "validate any z" in d
    # The peak fields added in plan 08 are what lets a client derive
    # alternative hypotheses — the description must advertise them.
    assert "strongest_peaks_angstrom" in d and "n_peaks_detected" in d
    assert "robustness check" in ts["reconstruct_spectrum"].description
    assert ts["predict_redshift"].input_schema["required"] == ["npz_path"]
    assert set(ts["identify_spectral_lines"].input_schema["required"]) == {
        "npz_path", "z"
    }
    # mask_ratio has a default, so only the path is required.
    assert ts["reconstruct_spectrum"].input_schema["required"] == ["npz_path"]


def test_call_tool_equals_impl_on_real_heldout_spectrum():
    ex = str(EXAMPLES / "heldout_z020.npz")
    got = _payload(
        _run(mcp.call_tool(
            "identify_spectral_lines", {"npz_path": ex, "z": 0.2036}
        ))
    )
    assert got == tools.identify_spectral_lines_impl(ex, 0.2036)
    assert got["verdict"] == "consistent"
    assert got["n_peaks_detected"] > 0 and got["strongest_peaks_angstrom"]


def test_model_tools_delegate_with_defaults(monkeypatch):
    calls = {}

    def fake_predict(npz_path):
        calls["predict"] = npz_path
        return {"z_pred_map": 1.5, "z_confidence": 0.9, "z_pred": 1.48}

    def fake_reconstruct(npz_path, mask_ratio=0.5):
        calls["reconstruct"] = (npz_path, mask_ratio)
        return {"mask_ratio": mask_ratio, "n_tokens_masked": 136}

    monkeypatch.setattr(tools, "predict_redshift_impl", fake_predict)
    monkeypatch.setattr(tools, "reconstruct_spectrum_impl", fake_reconstruct)

    got = _payload(_run(mcp.call_tool("predict_redshift", {"npz_path": "a.npz"})))
    assert got == {"z_pred_map": 1.5, "z_confidence": 0.9, "z_pred": 1.48}
    assert calls["predict"] == "a.npz"

    got = _payload(_run(mcp.call_tool("reconstruct_spectrum", {"npz_path": "b.npz"})))
    assert got["mask_ratio"] == 0.5  # server applies the declared default
    assert calls["reconstruct"] == ("b.npz", 0.5)
