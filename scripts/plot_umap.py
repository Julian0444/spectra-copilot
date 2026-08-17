"""UMAP of the FAISS index embeddings, colored by catalog redshift.

Reads data/spectra_embeddings.npy + data/spectra_meta.npz (written by
scripts/build_index.py) and renders docs/img/umap_z.png. The model was never
told to order spectra by redshift — if the embedding space shows a smooth z
gradient, that structure was learned from the spectra alone.

Requires: pip install umap-learn matplotlib
Usage:    python scripts/plot_umap.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import umap

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    x = np.load(ROOT / "data" / "spectra_embeddings.npy")
    z = np.load(ROOT / "data" / "spectra_meta.npz")["z"]
    print(f"UMAP over {x.shape[0]} embeddings (dim {x.shape[1]})...", flush=True)

    xy = umap.UMAP(
        n_neighbors=30, min_dist=0.1, metric="cosine", random_state=42
    ).fit_transform(x)

    fig, ax = plt.subplots(figsize=(7, 6), facecolor="white")
    order = np.argsort(z)  # draw high-z last so the rare tail stays visible
    sc = ax.scatter(
        xy[order, 0], xy[order, 1], c=np.log1p(z[order]),
        s=2, cmap="viridis", alpha=0.6, linewidths=0,
    )
    ax.set_axis_off()
    ax.set_title(
        "Foundation-model embedding space (UMAP), colored by redshift",
        fontsize=11,
    )
    # Color encodes log(1+z); the ticks read in plain z.
    cbar = fig.colorbar(sc, ax=ax, label="redshift z (log scale)", shrink=0.85)
    z_ticks = np.array([0.0, 0.25, 0.5, 1.0, 2.0, 3.0])
    z_ticks = z_ticks[np.log1p(z_ticks) <= np.log1p(z).max()]
    cbar.set_ticks(np.log1p(z_ticks))
    cbar.set_ticklabels([f"{t:g}" for t in z_ticks])

    out = ROOT / "docs" / "img" / "umap_z.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
