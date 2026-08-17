"""Export 150 real held-out DESI spectra as labeled eval cases (plan 11).

Cases are drawn from the canonical held-out stream — filter(valid z) ->
skip(80000) — which is row-aligned with the 2000-row v2.1 predictions CSV
(`eval/heldout_predictions_v21.csv`, copied from
runs/desi_80k_classhead_v21/predictions.csv of desi-spectra-fm). That
alignment buys three things the naive "shuffle the stream" sketch could not:

- the eval never touches the training side of the split (the first 80k
  valid-z examples), which the model AND the FAISS index have seen;
- selection is stratified on the known z_true distribution, oversampling
  z > 1.5 (the band where v2.1 still fails) instead of hoping a shuffle
  buffer surfaces hard cases;
- every exported z_true is asserted against the CSV row, so an upstream
  reshuffle of MultimodalUniverse/desi aborts the export instead of
  silently mislabeling the ground truth.

Usage (streaming through the 80k skip takes 15 min - 2.5 h):

    python eval/export_cases.py [--n 150] [--out eval/cases]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

EVAL_DIR = Path(__file__).resolve().parent
PREDICTIONS_CSV = EVAL_DIR / "heldout_predictions_v21.csv"

# (z_lo, z_hi, quota) — 150 total, 45 in the z > 1.5 failure band (the plan
# asks for >= 20; the whole point is measuring outlier recovery, so go denser).
STRATA = [
    (0.0, 0.5, 40),
    (0.5, 1.0, 35),
    (1.0, 1.5, 30),
    (1.5, 2.0, 25),
    (2.0, 2.5, 10),
    (2.5, np.inf, 10),
]


def select_cases(z_true: list[float], n: int = 150, seed: int = 7) -> list[int]:
    """Pick `n` held-out indices, stratified by z_true; deterministic."""
    rng = np.random.default_rng(seed)
    z = np.asarray(z_true)
    chosen: list[int] = []
    scale = n / sum(q for _, _, q in STRATA)
    for lo, hi, quota in STRATA:
        pool = np.flatnonzero((z >= lo) & (z < hi))
        take = min(int(round(quota * scale)), pool.size)
        chosen.extend(rng.choice(pool, size=take, replace=False).tolist())
    # Top up from the biggest strata if rounding or a thin bin fell short.
    if len(chosen) < n:
        rest = np.setdiff1d(np.arange(z.size), chosen)
        chosen.extend(rng.choice(rest, size=n - len(chosen), replace=False).tolist())
    return sorted(int(i) for i in chosen[:n])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--out", default=str(EVAL_DIR / "cases"))
    args = ap.parse_args()

    from datasets import load_dataset

    from desi_fm.data import extract_mmu_desi_example, has_valid_redshift

    with open(PREDICTIONS_CSV) as f:
        z_csv = [float(r["z_true"]) for r in csv.DictReader(f)]
    indices = select_cases(z_csv, n=args.n)
    wanted = {idx: f"case_{k:03d}" for k, idx in enumerate(indices)}
    n_hard = sum(z_csv[i] > 1.5 for i in indices)
    print(f"selected {len(indices)} held-out indices, {n_hard} with z_true > 1.5")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stream = load_dataset(
        "MultimodalUniverse/desi", data_dir="edr_sv3", split="train",
        streaming=True,
    )
    stream = stream.filter(has_valid_redshift).skip(80000).take(max(indices) + 1)
    print("streaming through the 80k-example skip (this is the slow part)...")

    rows = []
    for i, example in enumerate(stream):
        if i not in wanted:
            continue
        flux, ivar, wavelength, mask, z = extract_mmu_desi_example(example)
        if abs(z - z_csv[i]) > 1e-4:
            raise RuntimeError(
                f"held-out index {i}: stream z={z:.5f} != csv z={z_csv[i]:.5f} "
                "— the upstream dataset order changed; do NOT trust these labels."
            )
        name = wanted[i]
        np.savez(
            out / f"{name}.npz",
            flux=flux.astype(np.float32),
            ivar=ivar.astype(np.float32),
            wavelength=wavelength.astype(np.float32),
            mask=mask.astype(bool),
            z_true=np.float32(z),
            object_id=str(example.get("object_id", "")),
        )
        rows.append({"case": name, "heldout_index": i, "z_true": z})
        print(f"[{len(rows)}/{len(indices)}] {name}  idx={i}  z_true={z:.4f}")

    if len(rows) != len(indices):
        raise RuntimeError(f"exported {len(rows)} of {len(indices)} cases")
    with open(out / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case", "heldout_index", "z_true"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out / 'labels.csv'} ({len(rows)} cases)")


if __name__ == "__main__":
    main()
