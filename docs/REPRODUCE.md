# Reproduce the public example

This guide runs the released packages on a public historical example. It is a
functional demonstration, not a blind evaluation or evidence of generalization.
The example's historical filename and expected redshift are not predictor inputs.
No private files, API key, paid agent call or acceptance cases are needed.

## Install the matching releases

Use Python 3.10 or newer in a fresh directory. The commands below install from
the immutable `v0.3.0` tags; `desi-fm` is not on PyPI.
**Tag installation is pending verification after the tags are published.**
Before publication, the same package code is checked using the release wheels
in a clean environment; this does not certify the future tag installation.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "desi-fm @ git+https://github.com/Julian0444/desi-spectra-fm.git@v0.3.0"
python -m pip install "spectra-copilot @ git+https://github.com/Julian0444/spectra-copilot.git@v0.3.0"
python -m pip check
```

## Download and verify public assets

The checkpoint and FAISS pair come from model repository
`jirustaroure/desi-spectra-fm`, revision
`40ff2ed09e5e1584303052e1a5dfe218a4a396b3`. Keep the index and metadata together.
The immutable revision and SHA-256 values below match the published files.

| File | Bytes | SHA-256 |
|---|---:|---|
| `checkpoint_last.pt` | 103964688 | `40247cbe0e706a66084d001b36424081554c26d3eb75c1f8b0ebec89cf5afe5a` |
| `faiss/spectra.faiss` | 30720045 | `fc13007f951e2d1c1dc7e30338f6de4203b65d5c9c44fddc1d39ce4da921968b` |
| `faiss/spectra_meta.npz` | 60256 | `83e4bdc035328618636b1e86ddad49367df8b2d70dd9ac90a2bb8bd4f503e9ee` |

This downloads about 135 MB without authentication and checks the bytes before
use. The example is pinned to an existing public Copilot commit, independently
of the not-yet-verified release tag. It is `examples/heldout_z020.npz` in that
repository. Only flux, wavelength, optional inverse variance and mask are copied
to `spectrum.npz`; catalog values and the original filename are not passed on.

```sh
python - <<'PYCODE'
from pathlib import Path
import hashlib
import shutil
import urllib.request
import numpy as np

root = Path("assets")
revision = "40ff2ed09e5e1584303052e1a5dfe218a4a396b3"
base = f"https://huggingface.co/jirustaroure/desi-spectra-fm/resolve/{revision}/"
assets = {
    "checkpoint_last.pt": (103964688, "40247cbe0e706a66084d001b36424081554c26d3eb75c1f8b0ebec89cf5afe5a"),
    "faiss/spectra.faiss": (30720045, "fc13007f951e2d1c1dc7e30338f6de4203b65d5c9c44fddc1d39ce4da921968b"),
    "faiss/spectra_meta.npz": (60256, "83e4bdc035328618636b1e86ddad49367df8b2d70dd9ac90a2bb8bd4f503e9ee"),
}

def fetch(url, target, size, digest):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)
    if target.stat().st_size != size or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f"Asset identity mismatch: {target}")
    print(f"Verified {target}: {digest}")

for name, (size, digest) in assets.items():
    fetch(base + name, root / name, size, digest)
example = root / "historical-example.npz"
fetch("https://raw.githubusercontent.com/Julian0444/spectra-copilot/52de8ec7629e9f636f600e56f01fa01bfe05a077/examples/heldout_z020.npz",
      example, 102713, "087b753d23d4d9ffcd4867bafc29456650410f12150759c0fc8a24118bce0d1a")
with np.load(example, allow_pickle=False) as source:
    arrays = {name: source[name] for name in ("flux", "wavelength", "ivar", "mask") if name in source}
    if not {"flux", "wavelength"}.issubset(arrays):
        raise RuntimeError("Missing spectral arrays")
np.savez("spectrum.npz", **arrays)
PYCODE
```

## Run FM and Copilot without an LLM

After downloading, both commands below use local assets. The FM command uses
CPU and no random masking. Copilot chooses its supported local device. Its CLI
runs deterministic tools; it does not invoke the paid agent. The FAISS pair is
available for neighbor tools, although this CLI only predicts and measures lines.

```sh
unset ANTHROPIC_API_KEY
export DESI_FM_CKPT="$PWD/assets/checkpoint_last.pt"
export DESI_FM_INDEX_DIR="$PWD/assets/faiss"
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
python -m desi_fm.predict --checkpoint "$DESI_FM_CKPT" --input spectrum.npz --output prediction.npz --device cpu --mask-ratio 0
python -m copilot spectrum.npz > copilot-report.json
python - <<'PYCODE'
import json
import numpy as np
with np.load("prediction.npz", allow_pickle=False) as result:
    print("FM official MAP redshift:", float(result["z_pred_map"][0]))
report = json.loads(open("copilot-report.json").read())
print("Copilot official model_z:", report["model_z"])
assert report["model_z"] == report["predict_redshift"]["z_pred_map"]
PYCODE
```

Inspect `prediction.npz` and `copilot-report.json`. Numerical results can differ
slightly by device; a successful command is a software check, not an accuracy
measurement. `z_confidence` is posterior concentration, not calibrated
correctness. The historical FAISS index uses the supervised representation;
neighbors are not independent confirmation, and the historical index's encoder
and preprocessing provenance are not fully established.

For scientific results, protocols and limitations, read
[EVALUATION.md](https://github.com/Julian0444/desi-spectra-fm/blob/v0.3.0/docs/EVALUATION.md).
Mechanical acceptance passed; scientific accuracy and global acceptance remain
pending human adjudication. This example does not reopen that evaluation.
