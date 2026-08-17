# End-to-end evals (plan 11)

Measures the **whole system** — agent + tools + desi-fm v2.1 — against DESI
pipeline redshifts, and answers one question: *does the verification loop
recover the catastrophic outliers the model alone gets wrong?*

## Files

| file | what |
|---|---|
| `heldout_predictions_v21.csv` | 2000 held-out predictions of desi-fm v2.1 (`runs/desi_80k_classhead_v21/predictions.csv` of the model repo), row-aligned with the canonical held-out stream `filter(valid z) → skip(80000)`. Source of the case selection and of the official η = 14.95 % figure. |
| `export_cases.py` | Exports 150 real held-out spectra as `cases/case_*.npz` + `cases/labels.csv`. Stratified on z_true (45 cases in the z > 1.5 failure band); every exported label is asserted against the CSV so an upstream reshuffle aborts instead of mislabeling. |
| `run_evals.py` | Runs both systems per case — model-only baseline (`tools.official_z`) and the agent (`run_structured`, ends in a structured `submit_report`, zero prose parsing) — and prints aggregate metrics incl. the confidence↔accuracy breakdown. The results CSV is rewritten after every case; `--resume` continues a killed run. |
| `transcripts/` | Full agent transcripts on the 4 demo spectra (plan 08) — the qualitative complement to the table. |
| `cases/` | The 150 exported cases (`*.npz` not in git — regenerate with `export_cases.py`; `labels.csv` is committed). |

## Reproduce

```bash
python eval/export_cases.py                 # 15 min – 2.5 h (streams the 80k skip)
python eval/run_evals.py --baseline-only    # model-only, no API key needed
python eval/run_evals.py --limit 20         # harness validation (~US$ 0.4, Haiku)
python eval/run_evals.py --resume           # full 150-case run (~US$ 3, Haiku)
```

`ANTHROPIC_API_KEY` must be set for the agent runs. Every metric uses
dz_n = |z − z_true| / (1 + z_true); 0.15 is the catastrophic-outlier
threshold, 0.05 the quality threshold.
