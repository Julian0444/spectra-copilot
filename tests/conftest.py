"""Shared fixtures. The tiny FAISS index lets similarity tests run offline:
it contains the real embedding of the held-out example among random vectors,
so retrieval correctness is checked end to end without the 15k index."""

import numpy as np
import pytest

from copilot import tools

HELDOUT_Z = 0.2036  # catalog z of examples/heldout_z020.npz


@pytest.fixture()
def tiny_index(tmp_path, monkeypatch):
    """Point the tools at a 33-vector index whose row 0 is the embedding of
    heldout_z020.npz (z = 0.2036); rows 1-32 are random unit vectors with
    fake redshifts. Yields the path of the indexed example."""
    from pathlib import Path

    from desi_fm.predict import embed_spectrum

    example = str(Path(__file__).resolve().parent.parent / "examples" / "heldout_z020.npz")
    flux, wave, ivar, mask = tools._load(example)
    emb = embed_spectrum(flux=flux, wavelength=wave, ivar=ivar, mask=mask, model=tools._model())
    emb = (emb / np.linalg.norm(emb)).astype(np.float32)

    rng = np.random.default_rng(7)
    others = rng.normal(size=(32, emb.size)).astype(np.float32)
    others /= np.linalg.norm(others, axis=1, keepdims=True)
    vectors = np.vstack([emb[None, :], others])
    redshifts = np.concatenate(
        [[HELDOUT_Z], rng.uniform(0.0, 3.0, 32)]
    ).astype(np.float32)

    faiss = tools._faiss()  # torch/faiss coexistence on macOS

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(tmp_path / "spectra.faiss"))
    np.savez(tmp_path / "spectra_meta.npz", z=redshifts)

    monkeypatch.setenv("DESI_FM_INDEX_DIR", str(tmp_path))
    tools._index.cache_clear()
    yield example
    tools._index.cache_clear()
