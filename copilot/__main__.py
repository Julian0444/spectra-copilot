"""CLI demo: run the tool chain on a spectrum and print the combined JSON.

Usage:
    python -m copilot examples/heldout_z020.npz
"""

import json
import sys

import numpy as np

from copilot import tools


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m copilot <spectrum.npz>", file=sys.stderr)
        raise SystemExit(2)
    npz = sys.argv[1]

    prediction = tools.predict_redshift_impl(npz)
    z = tools.official_z(prediction)
    report = {
        "input": npz,
        "predict_redshift": prediction,
        "identify_spectral_lines": tools.identify_spectral_lines_impl(npz, z),
    }

    d = np.load(npz)
    if "z_true" in d.files:
        report["z_true_reference"] = round(float(np.asarray(d["z_true"]).ravel()[0]), 4)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
