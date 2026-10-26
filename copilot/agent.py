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

from copilot import rag, tools, explanation
from copilot.budget import (Budget, Limits, BudgetStop, PINNED_MODEL, new_budget, guard_sdk,
                            RATES, LONG_PROMPT_RATES, PROMPT_TIER_LIMIT, request_configuration,
                            CASE_CEILING_USD, ANALYSIS_CALLS, AUTHORIZED_EFFORTS)
from copy import deepcopy
import inspect
from copilot.report import SYSTEM, system_prompt
from desi_fm.predict import model_identity, _prepare_inputs
from desi_fm.inputs import read_npz, bounded_real, positive_int, SpectrumInputError

DEFAULT_MODEL = PINNED_MODEL

# USD per million tokens (input, output). Cache writes bill at 1.25x input,
# cache reads at 0.1x.
PRICES = {model:tuple(rate/1000 for rate in rates) for model,rates in RATES.items()}
LONG_PROMPT_PRICES = {model:tuple(rate/1000 for rate in rates) for model,rates in LONG_PROMPT_RATES.items()}

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
    """Describe emission and Ca H/K absorption with SNR, coverage and provenance.

    No physical confirmation verdict. Candidates are computed in code from the
    measured wavelengths and compared uniformly. Ambiguous single-line evidence
    never establishes a unique redshift and cannot replace model_z.

    Args:
        npz_path: path to the spectrum .npz file.
        z: nonnegative redshift hypothesis to describe.
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
    observation_ids: list[str],
    assessment: Literal["descriptive", "ambiguous", "insufficient_data"] = "descriptive",
    reference_ids: list[str] | None = None,
) -> str:
    """Select recorded observation IDs and a conservative assessment exactly once.

    The executor renders the report. No model_z, z_final, numerical measurements,
    free prose, tool names or alternative redshifts can be supplied here.
    """
    if not observation_ids or len(observation_ids) != len(set(observation_ids)):
        raise SpectrumInputError("Nonempty, distinct observation IDs required")
    return json.dumps(dict(observation_ids=observation_ids, assessment=assessment, reference_ids=reference_ids))


@contextmanager
def agent_input(source):
    """Derived protocol v2. Labels, original paths and metadata stay outside LLM messages."""
    from io import BytesIO
    try:
        payload = source if isinstance(source, bytes) else Path(source).read_bytes()
    except OSError as exc:
        raise SpectrumInputError('Scientific input is unreadable') from exc
    batch = read_npz(BytesIO(payload))
    f, w, v, m = batch.single()
    _prepare_inputs(tools._model(), f, w, v, m)  # reject no coverage before any LLM request
    with TemporaryDirectory(prefix="spectra-input-") as directory:
        target = Path(directory) / "spectrum.npz"
        np.savez(target, flux=f, wavelength=w, ivar=v, mask=m,
                 wavelength_unit="angstrom")
        provenance = {"protocol": "opaque-scientific-input-v2",
                      "source_sha256": hashlib.sha256(payload).hexdigest(),
                      "derived_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        yield str(target), provenance


def wire_observation(observation):
    """Compact the LLM view; the executor retains every original measurement.

    No alternatives are dropped. Repeated provenance and detailed support tables
    stay in the ledger. Counts, peak origins and uniform scores remain visible.
    """
    view=deepcopy(observation)
    if view['tool']=='identify_spectral_lines' and not view.get('error'):
        data=view['result']
        data['measurements']=data.get('measurements',[])[:5]
        data.pop('support_intervals',None)
        data.pop('line_support',None)
        for candidate in data.get('candidates',[]):
            candidate.pop('provenance',None)
            comparison=candidate['comparison']
            candidate['comparison']={k:comparison[k] for k in
                ('z_tested','n_expected_in_coverage','n_matched','match_fraction','matched_lines')}
        data['wire_omissions']='Full support tables, remaining peaks and repeated provenance are retained in executor ledger.'
    return view


class RunTools:
    """Executor-owned canonical prediction and immutable observation ledger."""
    def __init__(self, path, structured=True):
        self.calls, self.result, self.path = 0, None, path
        self.prediction = None
        self.terminal_status = None
        self.observations, self.violations = [], []
        self.history, self.usage = [], dict.fromkeys(USAGE_KEYS, 0)
        self.tools = [self.guard(t) for t in (predict_redshift, identify_spectral_lines,
                     reconstruct_spectrum, find_similar_spectra, lookup_reference, submit_report)]

    def record(self, name, arguments, value, error=None):
        observation = dict(id=f"obs-{len(self.observations)+1}", tool=name,
                           arguments=deepcopy(arguments), result=deepcopy(value))
        if error:
            observation['error'] = error
        self.observations.append(observation)
        return observation

    def bootstrap(self):
        value = tools.predict_redshift_impl(self.path)
        explanation.canonical_z(value)
        self.prediction = deepcopy(value)
        self.calls += 1
        self.record('predict_redshift', {'npz_path': 'spectrum.npz'}, value)
        # Both executor-owned analyses count within the unchanged six-call cap.
        # Use the same guard/ledger as later LLM-selected analyses.
        self.tools[1].call({'npz_path':self.path, 'z':explanation.canonical_z(value)})

    def finish(self, status='explanation_incomplete'):
        # Revalidate even cached reports: the corpus can change during a run.
        # Retain the original ledger for audit, but never publish stale citations.
        try:
            for observation in self.observations:
                if observation['tool']=='lookup_reference' and not observation.get('error'):
                    rag.validate_retrieval(observation['result'])
        except (ValueError,KeyError,OSError):
            return explanation.result(self.prediction,self.observations,
                [o['id'] for o in self.observations if o['tool']!='lookup_reference'],
                status='technical_error',violations=self.violations+['reference_validation_failed'])
        if self.result is not None and not self.violations and status == 'explanation_incomplete':
            return deepcopy(self.result)
        return explanation.result(self.prediction, self.observations,
            [o['id'] for o in self.observations], status=status, violations=self.violations)

    def guard(self, base):
        @wraps(base.func)
        def execute(*args, **kwargs):
            if self.result is not None:
                raise SpectrumInputError("Report already submitted; no further tools allowed")
            try:
                bound = inspect.signature(base.func).bind(*args, **kwargs)
            except TypeError:
                self.violations.append('incompatible_tool_arguments')
                raise SpectrumInputError('Incompatible tool arguments') from None
            arguments = bound.arguments
            if 'npz_path' in arguments and arguments['npz_path'] != self.path:
                self.violations.append('unauthorized_input')
                raise SpectrumInputError("Only the supplied opaque spectrum path is allowed")
            if base.name == 'submit_report':
                payload = json.loads(base.func(*args, **kwargs))
                try:
                    self.result = explanation.result(self.prediction, self.observations,
                        payload['observation_ids'], payload['assessment'], violations=self.violations,
                        reference_ids=payload['reference_ids'])
                except (ValueError, KeyError):
                    self.violations.append('invalid_report')
                    raise SpectrumInputError('Invalid report evidence or missing prediction') from None
                return 'recorded'
            if self.calls >= ANALYSIS_CALLS:
                self.violations.append('analysis_budget_exhausted')
                raise SpectrumInputError("Tool budget exhausted: at most 6 analysis calls")
            self.calls += 1
            if base.name == 'predict_redshift' and self.prediction is not None:
                return json.dumps(self.observations[0])
            safe_arguments = dict(arguments)
            if 'npz_path' in safe_arguments:
                safe_arguments['npz_path'] = 'spectrum.npz'
            try:
                value = json.loads(base.func(*args, **kwargs))
                if base.name == 'lookup_reference':
                    rag.validate_retrieval(value)
            except Exception as exc:
                code = 'invalid_input' if isinstance(exc, SpectrumInputError) else 'technical_error'
                self.record(base.name, safe_arguments, None, code)
                self.violations.append(code)
                raise SpectrumInputError(code) from None
            if base.name == 'predict_redshift':
                explanation.canonical_z(value)
                self.prediction = deepcopy(value)
            return json.dumps(wire_observation(self.record(base.name, safe_arguments, value)))
        return beta_tool(execute)


def execute_run(path, model, structured, state=None, budget=None, progress=None):
    state = state or RunTools(path, structured)
    state.bootstrap()
    budget = budget or new_budget(model)
    state.budget = budget
    if progress:
        budget.on_change = lambda snapshot: progress(state.finish(), snapshot)
        progress(state.finish(), budget.snapshot())
    budget.begin()
    client = anthropic.Anthropic(max_retries=0, timeout=min(Limits().seconds,budget.limits.seconds))
    with guard_sdk(client, budget):
        runner = client.beta.messages.tool_runner(
            model=model, max_tokens=min(Limits().max_output_per_call,budget.limits.max_output_per_call),
            max_iterations=min(Limits().calls,budget.limits.calls),
            system=system_prompt(state.prediction["model_identity"]) + STRUCTURED_RULE,
            tools=state.tools,
            messages=[{"role": "user", "content": f"Analyze the spectrum in {path} and " +
                       "submit the result via submit_report. Initial executor observations: " +
                       json.dumps([wire_observation(o) for o in state.observations])}],
            **request_kwargs(model,budget.effort))
        history, final = state.history, None
        usage = state.usage
        for message in runner:
            final = message
            # Traces are separate copies; sanitation never edits the SDK history.
            history.append({"role": "assistant", "content": deepcopy(message.to_dict()["content"])})
            if any(b.type == 'text' and b.text.strip() for b in message.content):
                state.violations.append('unvalidated_generated_text')
            if any(b.type == 'tool_use' and b.name not in {t.name for t in state.tools} for b in message.content):
                state.violations.append('unknown_tool')
            for key in USAGE_KEYS:
                usage[key] += getattr(message.usage, key, None) or 0
            stop_reason=getattr(message,'stop_reason',None)
            if stop_reason in {'refusal','max_tokens'}:
                state.terminal_status=stop_reason
                if progress:progress(state.finish(status=stop_reason),budget.snapshot())
                break
            response = runner.generate_tool_call_response()
            if response is not None:
                history.append(_jsonable(response))
            if progress:progress(state.finish(), budget.snapshot())
            if state.result is not None:
                break
    return state, final, usage, history


def request_kwargs(model: str, effort='low') -> dict:
    """Explicit 5B-2.2 settings; retain legacy behavior for historical models."""
    if model == PINNED_MODEL:
        return request_configuration(effort)
    if model.startswith("claude-haiku"):
        return {}
    return {"thinking": {"type": "adaptive"}}


def estimate_cost_usd(model: str, usage: dict) -> float | None:
    """Per-request estimate; the execution ledger is authoritative across turns.

    For legacy single-tier records accumulated usage is also valid. A Haiku 5.5
    aggregate without request boundaries uses the high tier conservatively.
    """
    from decimal import Decimal
    if model not in PRICES:
        return None
    prompt_tokens=sum(usage.get(k,0) for k in ('input_tokens','cache_creation_input_tokens','cache_read_input_tokens'))
    rates=LONG_PROMPT_PRICES[model] if model in LONG_PROMPT_PRICES and prompt_tokens>PROMPT_TIER_LIMIT else PRICES[model]
    rate_in, rate_out = map(lambda n:Decimal(str(n)),rates)
    return float((
        usage.get("input_tokens", 0) * rate_in
        + usage.get("cache_creation_input_tokens", 0) * rate_in * Decimal('1.25')
        + usage.get("cache_read_input_tokens", 0) * rate_in * Decimal('0.1')
        + usage.get("output_tokens", 0) * rate_out
    ) / Decimal(1000000))


def _jsonable(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


class AgentRunError(RuntimeError):
    """Incomplete report, with safe per-run diagnostics available to callers."""
    def __init__(self, code, history, usage):
        super().__init__(code)
        self.code, self.history, self.usage = code, history, usage


def run_structured(npz_path: str, model: str = DEFAULT_MODEL, *, budget=None, progress=None, effort='low') -> dict:
    """Always retain status and any valid official prediction, including failures."""
    usage, history, provenance, state = dict.fromkeys(USAGE_KEYS, 0), [], None, None
    try:
        budget = budget or new_budget(model,effort=effort)
        if budget.effort!=effort:raise BudgetStop('effort_budget_mismatch')
        with agent_input(npz_path) as (path, provenance):
            state = RunTools(path, True)
            state, final, usage, history = execute_run(path, model, True, state=state, budget=budget, progress=progress)
        report = state.finish(status=state.terminal_status or 'explanation_incomplete')
        report['completion_code'] = state.terminal_status or ('iteration_limit' if len([m for m in history if m['role']=='assistant']) >= min(Limits().calls,budget.limits.calls)
                                     and state.result is None else 'invalid_or_missing_report' if report['status']=='explanation_incomplete' else None)
    except BudgetStop as exc:
        report = state.finish(status='explanation_incomplete') if state else explanation.result(status='explanation_incomplete')
        report['completion_code'] = exc.code
    except SpectrumInputError:
        report = state.finish(status='explanation_incomplete') if state and state.prediction is not None else explanation.result(status='invalid_input')
    except Exception:
        report = state.finish(status='technical_error') if state else explanation.result(status='technical_error')
    if state is not None:
        usage, history = state.usage, state.history
    report.update(tokens_in=usage['input_tokens'], tokens_out=usage['output_tokens'],
                  usage=usage, input_provenance=provenance, history=history,
                  history_is_unvalidated=True,
                  execution_budget=budget.snapshot() if budget is not None else None)
    return report


def run(npz_path: str, model: str = DEFAULT_MODEL, transcript: str | None = None, *, budget=None, effort='low') -> str:
    report = run_structured(npz_path, model, budget=budget,effort=effort)
    if transcript:
        target = Path(transcript)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report['history'], indent=2, default=str))
        target.with_suffix('.input.json').write_text(json.dumps(report['input_provenance'], indent=2))
        target.with_suffix('.status.json').write_text(json.dumps(dict(
            status='ok' if report['status'] in {'complete','ambiguous','insufficient_data'} else 'error',
            code=report.get('completion_code') or report['status'], model_z=report['model_z'],
            result=report), indent=2))
    if report['status'] not in {'complete', 'ambiguous', 'insufficient_data'}:
        exc = AgentRunError(report.get('completion_code') or report['status'], report['history'], report['usage'])
        exc.result = report
        raise exc
    return explanation.render(report)


STRUCTURED_RULE = "\nCall submit_report exactly once using only observation IDs. No free prose or numeric conclusion."


def main() -> int:
    p = argparse.ArgumentParser(
        description="Agent that analyzes a spectrum and writes a cited report."
    )
    p.add_argument("npz_path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument('--effort',choices=AUTHORIZED_EFFORTS,default='low')
    p.add_argument("--budget-usd", type=float, default=0., help="Explicit paid ceiling; default zero. 5C requires prior authorization.")
    p.add_argument("--save-transcript", default=None, metavar="PATH")
    args = p.parse_args()
    if args.budget_usd:
        p.error('Paid 5C execution requires copilot.acceptance with registered identity and campaign')
    if not 0 <= args.budget_usd <= CASE_CEILING_USD or (args.budget_usd and args.model != PINNED_MODEL):
        p.error('Paid proposal requires the pinned model and USD ceiling at most 0.10')
    budget = Budget(args.model, Limits(usd=args.budget_usd),effort=args.effort) if args.budget_usd else None
    try:
        print(run(args.npz_path, args.model, args.save_transcript, budget=budget,effort=args.effort))
    except AgentRunError as exc:
        print(explanation.render(exc.result))
        print(json.dumps({'status': 'error', 'code': exc.code}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
