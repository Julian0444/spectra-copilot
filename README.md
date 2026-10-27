# Spectra Copilot

[![ci](https://github.com/Julian0444/spectra-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Julian0444/spectra-copilot/actions/workflows/ci.yml)

Experimental tools and an LLM agent for astronomical spectra. Copilot uses the
[DESI multitask transformer](https://github.com/Julian0444/desi-spectra-fm) for an
official redshift, measures spectral features, retrieves neighbors and reference
excerpts, and produces reports tied to recorded observations. The executor owns
`model_z`; generated alternatives cannot replace it. **v2.1 is the default;
CNN-17 is experimental.**

The main historical result is negative: on a stratified sample of 150 spectra,
the original agent achieved 119/150 successes versus 139/150 for the model alone,
at normalized redshift error below 0.15. It broke 21 correct predictions and
recovered one outlier. The sample came from non-independent historical validation;
this result describes that earlier policy. The protected-report policy has a
separate 5C evaluation. See the [canonical evaluation](https://github.com/Julian0444/desi-spectra-fm/blob/main/docs/EVALUATION.md)
for protocols, current status and limits, and the [historical evaluation record](eval/README.md).

## Install and run

The 0.3.0 release is being prepared. `desi-fm` is not on PyPI: install matching
source checkouts for development. After publication, CI installs it from the
GitHub `v0.3.0` tag.

```bash
git clone https://github.com/Julian0444/desi-spectra-fm.git
git clone https://github.com/Julian0444/spectra-copilot.git
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e './desi-spectra-fm[api,ui,dev]'
python -m pip install -e './spectra-copilot[ui,dev]'
cd spectra-copilot
export DESI_FM_CKPT=/path/to/checkpoint_last.pt
python -m copilot /path/to/spectrum.npz
```

That command runs deterministic tools and needs no LLM key. Inputs follow the
[FM input contract](https://github.com/Julian0444/desi-spectra-fm/blob/main/docs/INPUT_CONTRACT.md):
flux and wavelength in Å, with optional inverse variance and bad-pixel mask.
The verified checkpoint and FAISS assets are available from the
[model repository](https://huggingface.co/jirustaroure/desi-spectra-fm).
Without a local checkpoint, the tools download the pinned default asset.
For installed wheels, asset configuration, local UI and API checks, use the
[reproduction guide](docs/BATCH_5C_REPRODUCE.md).

## Tools and agent

| Tool | Output and limit |
|---|---|
| `predict_redshift` | Official MAP redshift, concentration and coverage; concentration is not calibrated accuracy. |
| `identify_spectral_lines` | Descriptive emission and supported absorption measurements, coverage and computed alternatives; physical confirmation is disabled. |
| `reconstruct_spectrum` | Prediction under masking; stability is not correctness. |
| `find_similar_spectra` | Neighbors from the same supervised encoder; no independent confirmation. |
| `lookup_reference` | Local BM25 excerpts and provenance; a valid citation ID does not establish scientific support. |

Run the stdio MCP server with `python -m copilot.mcp_server`. External clients
should use opaque inputs prepared by `scripts/derive_agent_inputs.py`, keeping
the source map with the evaluator. See [decisions](docs/DECISIONS.md).

The paid agent is a separate command, `python -m copilot.agent`. Its budget is
zero by default; a key alone does not authorize requests. Explicit model, budget
and limits are required. Secrets belong in the process environment, never in
committed files. The 5C acceptance is a controlled one-time evaluation, not a
quick-start command or a reusable authorization.

For a separately authorized individual request, the explicit flags are
`--model claude-haiku-5-5 --budget-usd 0.10`; the command still enforces its
per-call, token and time limits. This example does not launch or authorize it.

## Evaluation and limitations

The completed 5C development pilot compared low and medium effort on the same
12 cases each. Low passed the operational gate with 11/11 valid reports; medium
had 6/11. The earlier interrupted attempt is retained, with no usable response
and no behavioral evidence. The single 128-case acceptance passed mechanical
checks with 127/128 completed (79/80 real, 48/48 synthetic), at certified cost
US$0.1086672. Both AI annotations are complete; 894 claim disagreements leave
semantic review pending in 128/128 cases. The full adjudication package has no
human decisions. See [the 5C report](docs/BATCH_5C_REPORT.md).
Scientific accuracy and global acceptance remain pending human adjudication;
zero emitted claim–citation pairs are N/A, never 100% support.

The matcher failed its physical-confirmation development gate. Neighbors,
reference existence and template fidelity must not be treated as independent
scientific evidence. Synthetic public recipes test mechanisms, not blind
scientific generalization. No improvement over the official redshift is claimed.

Historical transcript checks passed 6/6 ID membership checks. They did not
evaluate textual support or scientific accuracy; the saved transcripts are
retained in `eval/transcripts/` as historical evidence.

- [Documentation index](docs/README.md)
- [Architecture and decisions](docs/DECISIONS.md)
- [Canonical scientific evaluation](https://github.com/Julian0444/desi-spectra-fm/blob/main/docs/EVALUATION.md)
- [Semantic review procedure](docs/BATCH_5C_AI_REVIEW.md) and [remaining human actions](docs/BATCH_5C_HUMAN_ACTIONS.md)
- [Release notes](docs/RELEASE_0_3_0.md)

Development and audits used AI assistants (Codex and Claude), with decisions and
verifications recorded in `docs/`. Personal contributions are not inferred from
that assistance or from commits; H-18 remains pending.
