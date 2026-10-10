# End-to-end evals (plan 11)

Measures the **whole system** — agent + tools + desi-fm v2.1 — against DESI
pipeline redshifts, and answers one question: *does the verification loop
recover the catastrophic outliers the model alone gets wrong?*

Since plan 12 the agent's toolset also includes `lookup_reference` (the
mini-RAG over DESI reference notes), so any run from that commit on measures
the agent *with* retrieval-grounded priors.

## Files

| file | what |
|---|---|
| `heldout_predictions_v21.csv` | 2000 held-out predictions of desi-fm v2.1 (`runs/desi_80k_classhead_v21/predictions.csv` of the model repo), row-aligned with the canonical held-out stream `filter(valid z) → skip(80000)`. Source of the case selection and of the official η = 14.95 % figure. |
| `export_cases.py` | Exports 150 real held-out spectra as `cases/case_*.npz` + `cases/labels.csv`. Stratified on z_true (45 cases in the z > 1.5 failure band); every exported label is asserted against the CSV so an upstream reshuffle aborts instead of mislabeling. |
| `run_evals.py` | Runs both systems per case — model-only baseline (`tools.official_z`) and the agent (`run_structured`, ends in a structured `submit_report`, zero prose parsing) — and prints aggregate metrics incl. the confidence↔accuracy breakdown. A complete case map is atomically replaced after every case and at exit; resume requires a compatible manifest. |
| `transcripts/` | Full agent transcripts on the demo spectra — the qualitative complement to the table. The 4 plan-08 runs (`claude-opus-4-8`) predate `find_similar_spectra` and `lookup_reference` and call only `predict_redshift` + `identify_spectral_lines`; the 3 `*_rag.json` runs (plan 12, `claude-haiku-4-5`) use the current 5-tool set. |
| `cases/` | The 150 exported cases (`*.npz` not in git — regenerate with `export_cases.py`; `labels.csv` is committed). |

## New runs and resume

Use a new destination; historical `results.csv` and `results_baseline.csv`
remain unchanged and have no compatible manifest. No legacy adoption is allowed.
The cases and checkpoint must already be available for an offline baseline.

```bash
python eval/run_evals.py --baseline-only
# Paid agent example; run only with a separately approved budget:
python eval/run_evals.py --limit 20 --out eval/runs/pilot/results.csv
python eval/run_evals.py --limit 20 --out eval/runs/pilot/results.csv --resume
# A 150-case run needs a NEW destination; do not change --limit on resume.
```

Without `--out`, each invocation creates a unique `eval/runs/<mode>-<id>/`
directory. Baseline and agent defaults never collide. `--resume` requires
explicit `--out`; mode, model, selected cases/labels/NPZ hashes, checkpoint,
index/corpus (agent), source code and relevant package versions must match.
This fingerprints the local protocol; it cannot pin an external provider's
implementation behind a mutable model alias.

`*.manifest.json` records identity; CSV stores all selected cases in order with
`pending`, `error`, `baseline` or `ok` status. Agent failures retry twice per
invocation; later resumes retry incomplete rows and preserve any valid baseline.
Completed baseline rows are skipped too. The full CSV is replaced atomically
using a sibling temporary file, `fsync` and rename, with an advisory writer lock
(macOS/Linux). A final flush and disk-derived summary run on normal exit and
Python interruption. A hard kill can lose an in-flight request, never a partially
written CSV; repeated API requests can incur cost. A corrupt/incompatible file
is rejected, not silently repaired.

The printed summary comes from the persisted CSV. `n`, pending/error counts and
both system denominators are explicit. Agent rates on successful reports are
conditional; `rate_015_all_cases` also counts errors/pending rows as no success.
Token totals cover successful persisted reports, not unavailable usage from
failed requests; no invocation-only cost is mixed into resumed totals. The
historical convention remains strict error <0.15 / <0.05.

Regression tests use temporary files and simulated computation:
`HF_HUB_OFFLINE=1 python -m pytest tests/test_eval_persistence.py tests/test_evals.py -q`.
No API key or paid LLM call is required.

## Results (run of 2026-08-17, committed as `results.csv`)

150/150 cases completed with a structured `submit_report`, 0 errors;
historically documented cost US$ 4.06 (`claude-haiku-4-5`, 3.27 M tokens). Headline numbers — the
full discussion lives in the [top-level README](../README.md#end-to-end-evals-does-verification-actually-help-n--150):

| system | rate < 0.15 | rate < 0.05 | MAE_norm |
|---|---|---|---|
| model v2.1 alone | 92.7 % | 77.3 % | 0.061 |
| agent (Haiku + 5 tools incl. RAG) | 79.3 % | 72.0 % | 0.104 |

Transitions: 118 both-right · 21 model-right/agent-wrong · 1 recovered
outlier · 10 both-wrong. Confidence↔accuracy: high 88.9 % (n=63), medium
77.1 % (n=70), low 52.9 % (n=17) — 17 of the 21 breaks were self-flagged
medium/low, so gating on `high` (hybrid policy: agent answer only when it
reports `high`, model otherwise) lands at 90.0 %. That gain comes entirely
from avoiding those 17 breaks (the other 4 were `high`); it recovers 0
outliers, because the one recovered outlier (`case_088`) was reported with
`medium` confidence and the gate hands it back to the model.

Notes for interpretation: the model-only row uses the tools' protocol
(deterministic full-context call, the same first tool call the agent makes) —
not comparable with the masked-evaluation η = 14.95 % of the model card. The
agent ran with the plan-12 toolset (`lookup_reference` included). The z > 1.5
stratified band is where the agent loses most ground (68.9 % vs 91.1 %):
weak matcher confirmation is associated with incorrect replacements. Causality
and the contribution of coverage remain hypotheses until traces and a controlled
intervention are available. This subset inherits v1 exposure and checkpoint
selection from the historical validation set; it is not an independent test.
The 90.0% hybrid is retrospective and remains below the 92.7% baseline.
