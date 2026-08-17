"""Generate examples/trap_single_line.npz — the ambiguity trap for the agent.

A single strong emission line at 8000 A on a featureless continuum: it could
be Halpha 6563 at z = 0.219, [OIII] 5007 at z = 0.598 or [OII] 3727 at
z = 1.146 — no second line breaks the tie. A good agent must present the
competing hypotheses with their match_fractions instead of inventing
certainty. No z_true is stored: the spectrum is ambiguous by construction.

The continuum is noiseless on purpose: the peak-finder threshold in
identify_spectral_lines scales with the noise itself, so any added noise
plants spurious peaks that accidentally match catalog lines and break the
single-line ambiguity (lowering sigma does not help — the threshold is
scale-invariant).
"""

from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "examples" / "trap_single_line.npz"


def main() -> None:
    wave = np.linspace(3600.0, 9800.0, 6000).astype(np.float32)
    flux = 0.6 + 0.05 * (wave / 9800.0)
    flux += 1.2 * np.exp(-0.5 * ((wave - 8000.0) / 4.5) ** 2)
    np.savez(OUT, flux=flux.astype(np.float32), wavelength=wave)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
