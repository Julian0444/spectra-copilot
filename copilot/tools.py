"""Deterministic tools for the spectra-copilot agent.

Each tool returns a compact JSON-friendly dict (conclusions, never raw
arrays). They wrap the desi-fm foundation model (v2.1, classification head)
plus classical signal processing, so an LLM agent can not only ask the model
for a redshift but also compare it against known spectral lines with an experimental peak heuristic.

Checkpoint resolution: the `DESI_FM_CKPT` environment variable (local path)
takes precedence; otherwise the public v2.1 checkpoint is downloaded from
Hugging Face Hub (jirustaroure/desi-spectra-fm, ~104 MB, cached).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from desi_fm.predict import embed_spectrum, load_model_from_checkpoint, predict_spectrum
from desi_fm.inputs import read_npz, bounded_real, positive_int, SpectrumInputError
from desi_fm.data import preprocess_spectrum, SpectrumPreprocessConfig
from desi_fm.assets import download_asset

# Default location of the FAISS index built by scripts/build_index.py.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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
    return download_asset("checkpoint_last.pt")


def _index_paths() -> tuple[str, str]:
    """Resolve (spectra.faiss, spectra_meta.npz): DESI_FM_INDEX_DIR, then the
    repo's data/ directory, then the copy published on the Hugging Face Hub."""
    local = Path(os.environ.get("DESI_FM_INDEX_DIR") or DATA_DIR)
    index_file, meta_file = local / "spectra.faiss", local / "spectra_meta.npz"
    if index_file.exists() and meta_file.exists():
        return str(index_file), str(meta_file)
    return (
        download_asset("faiss/spectra.faiss"),
        download_asset("faiss/spectra_meta.npz"),
    )


def _faiss():
    """Import faiss so it coexists with torch on macOS.

    torch and faiss-cpu each bundle their own libomp; the duplicate-runtime
    check aborts the whole process at faiss's first parallel region (OMP
    Error #15). The documented workaround plus single-threaded faiss keeps
    the two runtimes from contending — search over a 15k flat index is
    microseconds single-threaded anyway.
    """
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    import faiss

    faiss.omp_set_num_threads(1)
    return faiss


@lru_cache(maxsize=1)
def _index():
    faiss = _faiss()
    index_file, meta_file = _index_paths()
    return faiss.read_index(index_file), np.load(meta_file)["z"]


def _load(npz_path: str):
    """Shared single-spectrum contract. Never expose labels or other metadata."""
    return read_npz(npz_path).single()


def _z_summary(result: dict) -> dict:
    """Honest redshift summary: z_pred_map (+ confidence) is the official
    prediction of the v2.1 classification head; z_pred (expm1(E[log(1+z)])) is
    secondary. Falls back to z_pred alone for head-less checkpoints."""
    try:
        # Scalar v1 decodes to z > -1; classifier outputs must be nonnegative.
        bounded_real(result["z_pred"], "model z_pred", 0 if "z_pred_map" in result else -1, float("inf"))
        if "z_pred_map" in result:
            bounded_real(result["z_pred_map"], "model z_pred_map", 0, float("inf"))
            bounded_real(result["z_confidence"], "model z_confidence", 0, 1)
    except SpectrumInputError as exc:
        raise RuntimeError("Model returned an invalid redshift summary") from exc
    if "z_pred_map" in result:
        return {
            "z_pred_map": round(float(result["z_pred_map"]), 4),
            "z_confidence": round(float(result["z_confidence"]), 4),
            "z_pred": round(float(result["z_pred"]), 4),
            "coverage": result["coverage"],
            "model_identity": result["model_identity"],
        }
    return {"z_pred": round(float(result["z_pred"]), 4),
            "coverage": result["coverage"], "model_identity": result["model_identity"]}


def official_z(summary: dict) -> float:
    """The redshift an agent should act on, given a predict_redshift output."""
    return summary.get("z_pred_map", summary["z_pred"])


def predict_redshift_impl(npz_path: str) -> dict:
    """Predict the redshift of the spectrum in `npz_path` with desi-fm v2.1.

    Deterministic (mask_ratio=0). `z_pred_map` is the official prediction;
    `z_confidence` in [0, 1] is 1-H(p)/log(n_bins), an entropy-based
    concentration score, not a calibrated probability of correctness.
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
    mask_ratio = bounded_real(mask_ratio, "mask_ratio", 0, .9)
    flux, wave, ivar, mask = _load(npz_path)
    r = predict_spectrum(
        flux=flux, wavelength=wave, ivar=ivar, mask=mask,
        model=_model(), mask_ratio=mask_ratio,
    )
    masked = r["spectrum_mask"]
    out = {"mask_ratio": mask_ratio, "n_tokens_masked": int(masked.sum()),
           "coverage": r["coverage"], "model_identity": r["model_identity"]}
    out["z_pred_under_masking"] = round(float(r.get("z_pred_map", r["z_pred"])), 4)
    return out


def find_similar_spectra_impl(npz_path: str, k: int = 5) -> dict:
    """Retrieve the k nearest neighbors of a spectrum in embedding space.

    The spectrum is embedded with the encoder (mean-pooled spectral tokens)
    and searched against a FAISS index of 15k DESI *training* spectra, so
    held-out queries are never in the index. Similarity is cosine in [-1, 1].
    Each neighbor comes with its catalog redshift: a tight neighbor z range
    around a candidate z supports it through the embedding space — a signal
    independent of the classification head, though not of the shared encoder.
    """
    k = positive_int(k, "k", 100)
    flux, wave, ivar, mask = _load(npz_path)
    emb = embed_spectrum(flux=flux, wavelength=wave, ivar=ivar, mask=mask, model=_model())
    emb = (emb / np.linalg.norm(emb)).astype(np.float32)[None, :]
    index, meta_z = _index()
    if index.ntotal < 1 or len(meta_z) != index.ntotal or not np.isfinite(meta_z).all():
        raise RuntimeError("Unusable reference index or metadata")
    k = min(k, index.ntotal)
    sims, ids = index.search(emb, k)
    if (ids < 0).any() or (ids >= len(meta_z)).any() or not np.isfinite(sims).all():
        raise RuntimeError("Reference index returned invalid neighbors")
    neighbors = [
        {
            "rank": i + 1,
            "similarity": round(float(s), 3),
            "z": round(float(meta_z[j]), 3),
        }
        for i, (s, j) in enumerate(zip(sims[0], ids[0]))
    ]
    zs = [n["z"] for n in neighbors]
    return {
        "k": k,
        "index_size": int(index.ntotal),
        "neighbors": neighbors,
        "neighbor_z_range": [min(zs), max(zs)],
        "neighbor_z_median": round(float(np.median(zs)), 3),
    }


def identify_spectral_lines_impl(
    npz_path: str, z: float, tol_angstrom: float = 12.0
) -> dict:
    """Check whether known spectral lines appear where redshift `z` predicts.

    Detects *emission* peaks (prominence over a smoothed continuum) and
    matches them against the rest-frame catalog shifted by (1+z). The 12 A
    default tolerance is an uncalibrated historical heuristic. The strongest detected peaks are
    reported (by prominence, strongest first) so an agent can derive
    alternative z hypotheses from an unexplained peak. Caveat:
    absorption-dominated spectra (e.g. passive galaxies with only Ca H&K) can
    yield a weak verdict even at the correct z — a weak verdict is *lack of
    confirmation*, not refutation. A z that matches clearly fewer lines than
    an alternative z is the useful signal for validation.
    """
    z = bounded_real(z, "z", 0, float("inf"))
    tol_angstrom = bounded_real(tol_angstrom, "tol_angstrom", .000001, float("inf"))
    flux, wave, ivar, mask = _load(npz_path)
    coverage = preprocess_spectrum(flux, ivar, wave, mask, SpectrumPreprocessConfig())["coverage"]
    order = np.argsort(wave)
    flux, wave, ivar, mask = flux[order], wave[order], ivar[order], mask[order]
    good = np.isfinite(wave) & (wave > 0) & np.isfinite(flux) & np.isfinite(ivar) & (ivar > 0) & ~mask
    # Run the unchanged peak heuristic on each contiguous usable region.
    # Shared validity is a contract correction, not calibration of the matcher.
    edges = np.diff(np.r_[False, good, False].astype(int))
    regions = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))
    all_peaks, all_prom = [], []
    for lo, hi in regions:
        segment = flux[lo:hi].astype(float)
        smooth = gaussian_filter1d(segment, sigma=3.0)
        prominence = 0.8 * float(np.std(segment - smooth))
        found, props = find_peaks(smooth, prominence=prominence, distance=10)
        all_peaks.extend((found + lo).tolist())
        all_prom.extend(props["prominences"].tolist())
    peaks = np.asarray(all_peaks, dtype=int)
    props = {"prominences": np.asarray(all_prom)}
    peak_wl = wave[peaks]
    strongest = [
        round(float(peak_wl[i]), 1)
        for i in np.argsort(props["prominences"])[::-1][:5]
    ]
    expected, matched = [], []
    for name, lam in LINES.items():
        obs = lam * (1.0 + z)
        if not (wave[good].min() <= obs <= wave[good].max()):
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
        "coverage": coverage,
        "z_tested": z,
        "n_peaks_detected": int(peaks.size),
        "strongest_peaks_angstrom": strongest,
        "n_expected_in_coverage": len(expected),
        "n_matched": len(matched),
        "match_fraction": round(frac, 2),
        "matched_lines": matched,
        "verdict": "consistent" if frac >= 0.4 else "weak_or_inconsistent",
    }
