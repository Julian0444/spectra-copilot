"""CLI demo: run the tool chain on a spectrum and print the combined JSON.

Usage:
    python -m copilot examples/heldout_z020.npz
"""

import json
import sys


from copilot import tools
from copilot.agent import agent_input


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m copilot <spectrum.npz>", file=sys.stderr)
        raise SystemExit(2)
    npz = sys.argv[1]

    with agent_input(npz) as (opaque, provenance):
        prediction = tools.predict_redshift_impl(opaque)
        z = tools.official_z(prediction)
        report = {"input_id": "spectrum", "source_sha256": provenance["source_sha256"],
                  "model_z": z, "predictor": prediction['model_identity'],
                  "input_contract": prediction['coverage']['contract'],
                  "predict_redshift": prediction,
                  "identify_spectral_lines": tools.identify_spectral_lines_impl(opaque, z)}

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
