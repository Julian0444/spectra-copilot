"""Deterministic tools for the spectra-copilot agent.

Each tool returns a compact JSON-friendly dict (conclusions, never raw
arrays). They wrap the desi-fm foundation model (v2.1, classification head)
plus classical signal processing, so an LLM agent can not only ask the model
for a redshift but also *physically verify* it against known spectral lines.

Checkpoint resolution: the `DESI_FM_CKPT` environment variable (local path)
takes precedence; otherwise the public v2.1 checkpoint is downloaded from
Hugging Face Hub (jirustaroure/desi-spectra-fm, ~104 MB, cached).
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from desi_fm.predict import load_model_from_checkpoint, predict_spectrum

# Rest-frame line catalog (Angstroms) — galaxies + quasars.
LINES = {
    "Lyα 1216": 1215.7, "CIV 1549": 1549.1, "CIII] 1909": 1908.7,
    "MgII 2799": 2798.8, "[OII] 3727": 3727.1, "Ca K 3934": 3933.7,
    "Ca H 3969": 3968.5, "Hδ 4102": 4101.7, "Hγ 4340": 4340.5,
    "Hβ 4861": 4861.3, "[OIII] 4959": 4958.9, "[OIII] 5007": 5006.8,
    "Hα 6563": 6562.8, "[NII] 6583": 6583.5, "[SII] 6716": 6716.4,
}


@lru_cache(maxsize=1)
def _model():
    ckpt = os.environ.get("DESI_FM_CKPT") or _hub_checkpoint()
    return load_model_from_checkpoint(ckpt, torch.device("cpu"))


def _hub_checkpoint() -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download("jirustaroure/desi-spectra-fm", "checkpoint_last.pt")


def _load(npz_path: str):
    """Load flux/wavelength (+ optional ivar and bad-pixel mask) from a .npz.

    2-D inputs are reduced to their first spectrum. Non-finite flux pixels are
    zeroed and flagged as bad so they never reach the model or the peak finder.
    """
    d = np.load(npz_path)
    if "flux" not in d.files or "wavelength" not in d.files:
        raise KeyError(f"{npz_path} must contain 'flux' and 'wavelength'.")
    flux = np.atleast_2d(np.asarray(d["flux"], dtype=np.float32))[0]
    wave = np.atleast_2d(np.asarray(d["wavelength"], dtype=np.float32))[0]
    ivar = (
        np.atleast_2d(np.asarray(d["ivar"], dtype=np.float32))[0]
        if "ivar" in d.files else None
    )
    mask = (
        np.atleast_2d(np.asarray(d["mask"], dtype=bool))[0]
        if "mask" in d.files else np.zeros_like(flux, dtype=bool)
    )
    bad = ~np.isfinite(flux)
    if bad.any():
        flux = np.where(bad, 0.0, flux).astype(np.float32)
        mask = mask | bad
    return flux, wave, ivar, mask


def _z_summary(result: dict) -> dict:
    """Honest redshift summary: z_pred_map (+ confidence) is the official
    prediction of the v2.1 classification head; z_pred (regression) is
    secondary. Falls back to z_pred alone for head-less checkpoints."""
    if "z_pred_map" in result:
        return {
            "z_pred_map": round(float(result["z_pred_map"]), 4),
            "z_confidence": round(float(result["z_confidence"]), 4),
            "z_pred": round(float(result["z_pred"]), 4),
        }
    return {"z_pred": round(float(result["z_pred"]), 4)}


def official_z(summary: dict) -> float:
    """The redshift an agent should act on, given a predict_redshift output."""
    return summary.get("z_pred_map", summary["z_pred"])


def predict_redshift_impl(npz_path: str) -> dict:
    """Predict the redshift of the spectrum in `npz_path` with desi-fm v2.1.

    Deterministic (mask_ratio=0). `z_pred_map` is the official prediction;
    `z_confidence` in [0, 1] is the probability mass near the MAP bin (values
    below ~0.3 flag likely catastrophic outliers).
    """
    flux, wave, ivar, mask = _load(npz_path)
    r = predict_spectrum(flux=flux, wavelength=wave, ivar=ivar, mask=mask, model=_model())
    return _z_summary(r)


def reconstruct_spectrum_impl(npz_path: str, mask_ratio: float = 0.5) -> dict:
    """Mask a random fraction of token positions and re-predict.

    Reports how many of the model's 273 tokens were hidden and the redshift
    predicted from the partial spectrum — a stability probe: if z under heavy
    masking stays close to the full-spectrum z, the prediction is robust.
    """
    flux, wave, ivar, mask = _load(npz_path)
    r = predict_spectrum(
        flux=flux, wavelength=wave, ivar=ivar, mask=mask,
        model=_model(), mask_ratio=mask_ratio,
    )
    masked = r["spectrum_mask"]
    out = {"mask_ratio": mask_ratio, "n_tokens_masked": int(masked.sum())}
    out["z_pred_under_masking"] = round(float(r.get("z_pred_map", r["z_pred"])), 4)
    return out


def identify_spectral_lines_impl(
    npz_path: str, z: float, tol_angstrom: float = 12.0
) -> dict:
    """Check whether known spectral lines appear where redshift `z` predicts.

    Detects *emission* peaks (prominence over a smoothed continuum) and
    matches them against the rest-frame catalog shifted by (1+z). The 12 A
    default tolerance is ~5 DESI pixels. Caveat: absorption-dominated spectra
    (e.g. passive galaxies with only Ca H&K) can yield a weak verdict even at
    the correct z — a weak verdict is *lack of confirmation*, not refutation.
    A z that matches clearly fewer lines than an alternative z is the useful
    signal for validation.
    """
    flux, wave, _, _ = _load(npz_path)
    smooth = gaussian_filter1d(flux.astype(float), sigma=3.0)
    prominence = 0.8 * float(np.std(flux - smooth))
    peaks, _ = find_peaks(smooth, prominence=prominence, distance=10)
    peak_wl = wave[peaks]
    expected, matched = [], []
    for name, lam in LINES.items():
        obs = lam * (1.0 + z)
        if not (wave[0] <= obs <= wave[-1]):
            continue
        entry = {"line": name, "lambda_expected": round(obs, 1)}
        if peak_wl.size:
            d = float(np.abs(peak_wl - obs).min())
            if d <= tol_angstrom:
                entry["matched_peak_at"] = round(
                    float(peak_wl[np.abs(peak_wl - obs).argmin()]), 1
                )
                entry["delta"] = round(d, 1)
                matched.append(entry)
        expected.append(entry)
    frac = len(matched) / max(len(expected), 1)
    return {
        "z_tested": z,
        "n_expected_in_coverage": len(expected),
        "n_matched": len(matched),
        "match_fraction": round(frac, 2),
        "matched_lines": matched,
        "verdict": "consistent" if frac >= 0.4 else "weak_or_inconsistent",
    }
