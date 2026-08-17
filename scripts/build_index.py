"""Build the FAISS index behind the `find_similar_spectra` tool.

Streams N DESI spectra (MultimodalUniverse/desi, edr_sv3), embeds each one
with `DESIFoundationModel.encode()` (mean-pooled valid spectral tokens),
L2-normalizes and stores them in a `faiss.IndexFlatIP` — inner product on
unit vectors = cosine similarity.

The first N valid examples of the stream are exactly the training side of the
desi-fm split (held-out = skip 80k), so the `examples/heldout_*.npz` queries
are guaranteed to be absent from the index. No shuffle: membership is
identical either way (`take` runs before `shuffle` in HFDESISpectra) and a
deterministic order makes rebuilds reproducible.

Outputs (in --out, default data/):
    spectra.faiss           the index (N x d_model, cosine)
    spectra_meta.npz        z (catalog redshift) per indexed row
    spectra_embeddings.npy  the normalized embeddings (for UMAP / analysis)

Usage:
    python scripts/build_index.py --n 15000
    DESI_FM_CKPT=/path/to/checkpoint_last.pt python scripts/build_index.py

Requires faiss-cpu. Streaming ~15k spectra takes ~30-60 min the first time.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from desi_fm.data import HFDESISpectra, collate_spectra
from desi_fm.predict import load_model_from_checkpoint


def pick_device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=15_000, help="spectra to index")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--out", default="data", help="output directory")
    args = parser.parse_args()

    device = pick_device(args.device)
    ckpt = os.environ.get("DESI_FM_CKPT")
    if not ckpt:
        from huggingface_hub import hf_hub_download

        ckpt = hf_hub_download("jirustaroure/desi-spectra-fm", "checkpoint_last.pt")
    model = load_model_from_checkpoint(ckpt, device)
    print(f"model: {ckpt} on {device} (d_model={model.config.d_model})", flush=True)

    dataset = HFDESISpectra(max_examples=args.n)
    loader = DataLoader(dataset, batch_size=args.batch_size, collate_fn=collate_spectra)

    embeddings, redshifts, done, t0 = [], [], 0, time.time()
    with torch.no_grad():
        for batch in loader:
            emb = model.encode(batch["flux"].to(device), batch["valid"].to(device))
            embeddings.append(emb.cpu().numpy())
            redshifts.append(batch["z"].numpy())
            done += len(batch["z"])
            if done % 1600 == 0:
                rate = done / (time.time() - t0)
                print(f"{done}/{args.n} ({rate:.1f} spectra/s)", flush=True)

    x = np.concatenate(embeddings).astype(np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    z = np.concatenate(redshifts).astype(np.float32)

    # Embeddings and metadata are written BEFORE any faiss call: if faiss
    # aborts (see _faiss in copilot.tools), the expensive streaming pass is
    # not lost and the index can be rebuilt from the .npy alone.
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "spectra_meta.npz", z=z)
    np.save(out / "spectra_embeddings.npy", x)

    from copilot.tools import _faiss

    faiss = _faiss()
    index = faiss.IndexFlatIP(x.shape[1])
    index.add(x)
    faiss.write_index(index, str(out / "spectra.faiss"))
    print(
        f"indexed {index.ntotal} spectra (dim {x.shape[1]}) in "
        f"{(time.time() - t0) / 60:.1f} min -> {out}/",
        flush=True,
    )


if __name__ == "__main__":
    main()
