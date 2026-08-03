from pathlib import Path

import numpy as np
import pytest

from copilot import tools

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _synth(z, seed=1, n=6000):
    """Synthetic spectrum with strong emission lines at a known z."""
    rng = np.random.default_rng(seed)
    w = np.linspace(3600.0, 9800.0, n).astype(np.float32)
    f = 0.5 + 0.15 * np.sin(w / 700.0) + rng.normal(0, 0.05, n)
    for lam in (
        2798.8, 3727.1, 4101.7, 4340.5, 4861.3, 4958.9, 5006.8, 6562.8, 6716.4
    ):
        obs = lam * (1 + z)
        if w[0] <= obs <= w[-1]:
            f += 0.9 * np.exp(-0.5 * ((w - obs) / 5.0) ** 2)
    return w, f.astype(np.float32)


@pytest.fixture()
def case(tmp_path):
    w, f = _synth(0.42)
    p = tmp_path / "s.npz"
    np.savez(p, flux=f, wavelength=w)
    return str(p)


def test_lines_match_at_true_z(case):
    r = tools.identify_spectral_lines_impl(case, 0.42)
    assert r["match_fraction"] >= 0.5
    assert r["verdict"] == "consistent"


def test_lines_fail_at_wrong_z(case):
    good = tools.identify_spectral_lines_impl(case, 0.42)["match_fraction"]
    bad = tools.identify_spectral_lines_impl(case, 0.85)["match_fraction"]
    assert bad < good  # this gap is what the agent exploits to validate


def test_predict_redshift_range(case):
    # Downloads the checkpoint on first use (~104 MB) unless DESI_FM_CKPT
    # points at a local copy.
    r = tools.predict_redshift_impl(case)
    assert 0.0 <= r["z_pred"] <= 6.0


def test_predict_exposes_official_map_prediction(case):
    # The public v2.1 checkpoint has a classification head: z_pred_map is the
    # official prediction and must come with a confidence in [0, 1].
    r = tools.predict_redshift_impl(case)
    assert "z_pred_map" in r
    assert 0.0 <= r["z_pred_map"] <= 6.0
    assert 0.0 <= r["z_confidence"] <= 1.0
    assert tools.official_z(r) == r["z_pred_map"]


def test_reconstruct_reports_masking(case):
    r = tools.reconstruct_spectrum_impl(case, mask_ratio=0.5)
    assert 100 <= r["n_tokens_masked"] <= 180  # ~50 % of 273 tokens


def test_lines_discriminate_on_real_spectrum():
    # Real DESI held-out galaxy (z_true = 0.2036): the emission lines confirm
    # the true z sharply and reject a wrong one. No model involved.
    ex = str(EXAMPLES / "heldout_z020.npz")
    good = tools.identify_spectral_lines_impl(ex, 0.2036)
    bad = tools.identify_spectral_lines_impl(ex, 0.85)
    assert good["verdict"] == "consistent"
    assert bad["match_fraction"] < good["match_fraction"]


def test_load_handles_2d_and_nans(tmp_path):
    w, f = _synth(0.42)
    f2 = np.stack([f, f * 0.5])
    f2[0, 100] = np.nan
    p = tmp_path / "s2.npz"
    np.savez(p, flux=f2, wavelength=np.stack([w, w]))
    r = tools.identify_spectral_lines_impl(str(p), 0.42)
    assert r["verdict"] == "consistent"  # first spectrum, NaN neutralized
