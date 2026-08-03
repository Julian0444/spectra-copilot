# spectra-copilot

LLM agent that analyzes astronomical spectra using the
[desi-fm](https://github.com/Julian0444/desi-spectra-fm) foundation model as a
tool — this repo holds the deterministic tools the agent (and an MCP server)
build on. Every tool returns compact JSON conclusions, never raw arrays.

**Tools** (`copilot/tools.py`):

- `predict_redshift` — desi-fm v2.1 prediction: `z_pred_map` (official) +
  `z_confidence` + `z_pred` (secondary regression head).
- `identify_spectral_lines` — detects emission peaks and checks whether known
  lines (Lyα … [SII]) land where a given z predicts. This lets the agent
  *physically verify* the model instead of just repeating it.
- `reconstruct_spectrum` — masks a fraction of the model's tokens and
  re-predicts, probing the stability of the prediction.

## Quick start

```bash
pip install -e ".[dev]"
# optional: skip the ~104 MB Hub download by pointing at a local checkpoint
export DESI_FM_CKPT=/path/to/desi-spectra-fm/runs/desi_80k_classhead_v21/checkpoint_last.pt
pytest -q                                  # 7 passed
python -m copilot examples/heldout_z020.npz
```

Without `DESI_FM_CKPT`, the public checkpoint is downloaded from
[jirustaroure/desi-spectra-fm](https://huggingface.co/jirustaroure/desi-spectra-fm)
and cached. The `examples/` spectra are real DESI held-out objects (never seen
in training), each with its `z_true` for reference.

Example output (`examples/heldout_z020.npz`, real galaxy at z_true = 0.204):

```json
{
  "input": "examples/heldout_z020.npz",
  "predict_redshift": {
    "z_pred_map": 0.2267,
    "z_confidence": 0.6376,
    "z_pred": 0.2314
  },
  "identify_spectral_lines": {
    "z_tested": 0.2267,
    "n_expected_in_coverage": 11,
    "n_matched": 2,
    "match_fraction": 0.18,
    "matched_lines": [
      {"line": "Hβ 4861", "lambda_expected": 5963.4, "matched_peak_at": 5968.8, "delta": 5.4},
      {"line": "[NII] 6583", "lambda_expected": 8076.0, "matched_peak_at": 8085.6, "delta": 9.6}
    ],
    "verdict": "weak_or_inconsistent"
  },
  "z_true_reference": 0.2036
}
```

Note what the line tool buys the agent: at the model's `z_pred_map = 0.2267`
only 2/11 lines match, but at the true `z = 0.2036` the same spectrum matches
**8/11 (`consistent`)** — the tool can catch and refine an off prediction, and
a wrong z (e.g. 0.85) stays weak. That contrast is what the agent exploits.

## Related

- Model: [desi-spectra-fm](https://github.com/Julian0444/desi-spectra-fm)
  (code) · [HF checkpoint](https://huggingface.co/jirustaroure/desi-spectra-fm)
  · [live demo](https://huggingface.co/spaces/jirustaroure/desi-spectra-fm-demo)
  · [REST API](https://jirustaroure-desi-fm-api.hf.space/api/docs)

The agent (Claude API) and the MCP server land next.
