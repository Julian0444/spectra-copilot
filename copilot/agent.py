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
from contextlib import contextmanager
from functools import wraps
from tempfile import TemporaryDirectory
import hashlib
import numpy as np
from typing import Annotated, Literal
from pydantic import Field
import json
import sys
from pathlib import Path

import anthropic
from anthropic import beta_tool

from copilot import rag, tools
from copilot.report import SYSTEM, system_prompt
from desi_fm.predict import model_identity, _prepare_inputs
from desi_fm.inputs import read_npz, bounded_real, positive_int, SpectrumInputError

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
    """Run the desi-fm v2.1 multitask transformer on a spectrum file.

    Returns z_pred_map (the official prediction), z_confidence in [0, 1] and
    z_pred = expm1(E[log(1+z)]) from the same posterior.
    Concentration is based on entropy, not calibrated accuracy probability.

    Args:
        npz_path: path to a .npz file containing 'flux' and 'wavelength' (Angstrom).
    """
    return json.dumps(tools.predict_redshift_impl(npz_path))


@beta_tool
def identify_spectral_lines(npz_path: str, z: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]) -> str:
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
def reconstruct_spectrum(npz_path: str, mask_ratio: Annotated[float, Field(ge=0, le=.9, allow_inf_nan=False, strict=True)] = 0.5) -> str:
    """Mask a fraction of the model's 273 spectral tokens and re-predict z.

    Stability probe: if z under heavy masking stays close to the full-spectrum
    z in one draw, that is descriptive stability, not validated robustness.

    Args:
        npz_path: path to the spectrum .npz file.
        mask_ratio: fraction of tokens to hide (0-0.9).
    """
    return json.dumps(tools.reconstruct_spectrum_impl(npz_path, mask_ratio))


@beta_tool
def find_similar_spectra(npz_path: str, k: Annotated[int, Field(ge=1, le=100, strict=True)] = 5) -> str:
    """Find the k most similar spectra in a FAISS index of 15k DESI training spectra.

    The spectrum is embedded with the multitask transformer's encoder and matched
    by cosine similarity; each neighbor reports its catalog redshift. A tight
    neighbor z range is descriptive, not independent confirmation: embeddings
    share the supervised encoder. Historical index/encoder compatibility is
    unverified; scattered redshifts describe those retrieved neighbors.

    Args:
        npz_path: path to the spectrum .npz file.
        k: number of neighbors to retrieve (default 5).
    """
    return json.dumps(tools.find_similar_spectra_impl(npz_path, k))


@beta_tool
def lookup_reference(query: str, k: Annotated[int, Field(ge=1, le=30, strict=True)] = 3) -> str:
    """Consult the spectral-line catalog and DESI reference notes (BM25 retrieval).

    Use it to sanity-check target-type vs redshift priors (BGS/LRG/ELG/QSO
    ranges), line visibility windows, and to explain line degeneracies when a
    single-line identification is ambiguous. Each result carries an `id` you
    can cite in square brackets and the public `source` it was written from.

    Args:
        query: short keyword query, e.g. "ELG redshift range" or "Halpha OII confusion".
        k: number of documents to retrieve (default 3).
    """
    return json.dumps(rag.lookup_reference_impl(query, k))


@beta_tool
def submit_report(
    z_final: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)],
    confidence: Literal["high", "medium", "low"],
    lines_matched: Annotated[int, Field(ge=0, le=15, strict=True)],
    summary: str,
) -> str:
    """Submit the structured report once, after analysis.

    Args:
        z_final: finite nonnegative redshift hypothesis (experimental).
        confidence: categorical high, medium or low; not a probability.
        lines_matched: integer from 0 through 15 catalog lines.
        summary: nonempty justification citing the tools used.
    """
    if not summary.strip():
        raise SpectrumInputError("summary must be nonempty")
    return json.dumps(dict(z_final=z_final, confidence=confidence,
                           lines_matched=lines_matched, summary=summary), allow_nan=False)


@contextmanager
def agent_input(source):
    """Derived protocol v2. Labels, original paths and metadata stay outside LLM messages."""
    batch = read_npz(source)
    f, w, v, m = batch.single()
    _prepare_inputs(tools._model(), f, w, v, m)  # reject no coverage before any LLM request
    with TemporaryDirectory(prefix="spectra-input-") as directory:
        target = Path(directory) / "spectrum.npz"
        np.savez(target, flux=f, wavelength=w, ivar=v, mask=m,
                 wavelength_unit="angstrom")
        provenance = {"protocol": "opaque-scientific-input-v2",
                      "source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                      "derived_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        yield str(target), provenance


class RunTools:
    """Per-run budget and report. Multiple submits never replace the first."""
    def __init__(self, path, structured):
        self.calls = 0
        self.result = None
        self.path = path
        self.tools = [self.guard(t) for t in (predict_redshift, identify_spectral_lines,
                     reconstruct_spectrum, find_similar_spectra, lookup_reference)]
        if structured:
            self.tools.append(self.guard(submit_report))

    def guard(self, base):
        @wraps(base.func)
        def execute(*args, **kwargs):
            if self.result is not None:
                raise SpectrumInputError("Report already submitted; no further tools allowed")
            if base.name == "submit_report":
                value = base.func(*args, **kwargs)
                self.result = json.loads(value)
                return "recorded"
            if self.calls >= 6:
                raise SpectrumInputError("Tool budget exhausted: at most 6 analysis calls")
            self.calls += 1
            if "npz_path" in kwargs and kwargs["npz_path"] != self.path:
                raise SpectrumInputError("Only the supplied opaque spectrum path is allowed")
            return base.func(*args, **kwargs)
        return beta_tool(execute)


def execute_run(path, model, structured):
    state = RunTools(path, structured)
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=model, max_tokens=8000 if structured else 16000,
        max_iterations=8,
        system=system_prompt(model_identity(tools._model())) + (STRUCTURED_RULE if structured else ""),
        tools=state.tools,
        messages=[{"role": "user", "content": f"Analyze the spectrum in {path} and " +
                   ("submit the structured result via submit_report." if structured else "write the observation report.")}],
        **request_kwargs(model))
    history, final = [], None
    usage = dict.fromkeys(USAGE_KEYS, 0)
    for message in runner:
        final = message
        history.append({"role": "assistant", "content": message.to_dict()["content"]})
        for key in USAGE_KEYS:
            usage[key] += getattr(message.usage, key, None) or 0
        response = runner.generate_tool_call_response()
        if response is not None:
            history.append(_jsonable(response))
    return state, final, usage, history


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
    with agent_input(npz_path) as (path, provenance):
        state, final, usage, history = execute_run(path, model, False)
    if final is None:
        raise RuntimeError("tool runner produced no messages")
    if transcript:
        target = Path(transcript)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(history, indent=2, default=str))
        target.with_suffix(".input.json").write_text(json.dumps(provenance, indent=2))
    cost = estimate_cost_usd(model, usage)
    cost_txt = f" ~= ${cost:.4f}" if cost is not None else ""
    print(f"[usage] model={model} in={usage['input_tokens']} out={usage['output_tokens']}{cost_txt}", file=sys.stderr)
    return "".join(b.text for b in final.content if b.type == "text")


STRUCTURED_RULE = (
    "\nAdditional rule for this run: do NOT write the markdown report. "
    "Instead, ALWAYS finish by calling submit_report exactly once, after "
    "verifying your final z with identify_spectral_lines. Keep tool use "
    "tight: at most 6 tool calls before submit_report."
)


def run_structured(npz_path: str, model: str = "claude-haiku-4-5") -> dict | None:
    """Run the agent on one spectrum and return the submit_report payload.

    Returns None if the agent never called submit_report. On success the
    payload gains tokens_in / tokens_out plus the full accumulated `usage`
    dict, so callers can estimate cost with estimate_cost_usd().
    """
    with agent_input(npz_path) as (path, provenance):
        state, final, usage, history = execute_run(path, model, True)
    result = state.result
    if result is not None:
        result = dict(result)
        result.update(tokens_in=usage["input_tokens"], tokens_out=usage["output_tokens"],
                      usage=usage, input_provenance=provenance)
    return result


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
