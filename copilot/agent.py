"""Claude-API agent: analyze a spectrum end to end and write a cited report.

Usage:
    python -m copilot.agent examples/heldout_z020.npz
    python -m copilot.agent examples/trap_single_line.npz \
        --model claude-haiku-4-5 --save-transcript eval/transcripts/trap.json

Requires ANTHROPIC_API_KEY. The SDK tool runner drives the agentic loop: it
executes the deterministic tools from copilot.tools and feeds the JSON results
back to the model until the report is done. Token usage and estimated USD cost
are printed to stderr after each run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anthropic
from anthropic import beta_tool

from copilot import tools
from copilot.report import SYSTEM

DEFAULT_MODEL = "claude-opus-4-8"

# USD per million tokens (input, output). Cache writes bill at 1.25x input,
# cache reads at 0.1x.
PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


@beta_tool
def predict_redshift(npz_path: str) -> str:
    """Run the desi-fm v2.1 foundation model on a spectrum file.

    Returns z_pred_map (the official prediction), z_confidence in [0, 1] and
    the secondary regression z_pred.

    Args:
        npz_path: path to a .npz file containing 'flux' and 'wavelength' (Angstrom).
    """
    return json.dumps(tools.predict_redshift_impl(npz_path))


@beta_tool
def identify_spectral_lines(npz_path: str, z: float) -> str:
    """Check which known emission lines match real peaks if the spectrum is at redshift z.

    Detects emission peaks; absorption-dominated spectra can look 'weak' even
    at the right z. Also reports the strongest detected peak wavelengths
    (Angstrom, strongest first) so alternative z hypotheses can be derived
    from an unexplained peak.

    Args:
        npz_path: path to the spectrum .npz file.
        z: redshift hypothesis to test.
    """
    return json.dumps(tools.identify_spectral_lines_impl(npz_path, z))


@beta_tool
def reconstruct_spectrum(npz_path: str, mask_ratio: float = 0.5) -> str:
    """Mask a fraction of the model's 273 spectral tokens and re-predict z.

    Stability probe: if z under heavy masking stays close to the full-spectrum
    z, the prediction is robust.

    Args:
        npz_path: path to the spectrum .npz file.
        mask_ratio: fraction of tokens to hide (0-0.9).
    """
    return json.dumps(tools.reconstruct_spectrum_impl(npz_path, mask_ratio))


def request_kwargs(model: str) -> dict:
    """Per-model extras: adaptive thinking where supported (not on Haiku 4.5)."""
    if model.startswith("claude-haiku"):
        return {}
    return {"thinking": {"type": "adaptive"}}


def estimate_cost_usd(model: str, usage: dict) -> float | None:
    """Approximate USD cost of the accumulated usage; None for unknown models."""
    if model not in PRICES:
        return None
    rate_in, rate_out = PRICES[model]
    return (
        usage.get("input_tokens", 0) * rate_in
        + usage.get("cache_creation_input_tokens", 0) * rate_in * 1.25
        + usage.get("cache_read_input_tokens", 0) * rate_in * 0.1
        + usage.get("output_tokens", 0) * rate_out
    ) / 1e6


def _jsonable(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def run(
    npz_path: str, model: str = DEFAULT_MODEL, transcript: str | None = None
) -> str:
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        tools=[predict_redshift, identify_spectral_lines, reconstruct_spectrum],
        messages=[
            {
                "role": "user",
                "content": f"Analyze the spectrum in {npz_path} and write the "
                "observation report.",
            }
        ],
        **request_kwargs(model),
    )
    history, final = [], None
    usage = dict.fromkeys(USAGE_KEYS, 0)
    for message in runner:  # the runner executes the tools and loops by itself
        final = message
        history.append({"role": "assistant", "content": message.to_dict()["content"]})
        for key in USAGE_KEYS:
            usage[key] += getattr(message.usage, key, None) or 0
        tool_response = runner.generate_tool_call_response()  # cached; runs once
        if tool_response is not None:
            history.append(_jsonable(tool_response))
    if final is None:
        raise RuntimeError("tool runner produced no messages")
    if transcript:
        path = Path(transcript)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, indent=2, default=str))
    cost = estimate_cost_usd(model, usage)
    cost_txt = f" ~= ${cost:.4f}" if cost is not None else ""
    print(
        f"[usage] model={model} turns={len(history)} in={usage['input_tokens']} "
        f"out={usage['output_tokens']}{cost_txt}",
        file=sys.stderr,
    )
    return "".join(b.text for b in final.content if b.type == "text")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Agent that analyzes a spectrum and writes a cited report."
    )
    p.add_argument("npz_path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--save-transcript", default=None, metavar="PATH")
    args = p.parse_args()
    print(run(args.npz_path, args.model, args.save_transcript))


if __name__ == "__main__":
    main()
