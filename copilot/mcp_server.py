"""MCP server exposing the desi-fm foundation model as tools.

Any MCP client (Claude Code, Claude Desktop, the inspector, ...) gets the
same deterministic toolset the Claude-API agent uses: redshift prediction,
physical line verification and masked reconstruction. The client's LLM does
the reasoning; these tools only report measurements.

Run standalone:  python -m copilot.mcp_server
Dev inspector:   mcp dev copilot/mcp_server.py

Set DESI_FM_CKPT to a local checkpoint path to skip the ~104 MB Hub download
on the first model call.
"""

from mcp.server.mcpserver import MCPServer

from copilot import tools

mcp = MCPServer(
    "desi-fm",
    instructions=(
        "Tools around the desi-fm spectral foundation model (DESI galaxy/QSO "
        "spectra). Typical loop: predict_redshift first; if z_confidence is "
        "low (< 0.3) or the user asks for verification, test the redshift "
        "with identify_spectral_lines and derive alternative hypotheses from "
        "its strongest_peaks_angstrom. Inputs are .npz files containing "
        "'flux' and 'wavelength' (Angstrom) arrays."
    ),
)


@mcp.tool()
def predict_redshift(npz_path: str) -> dict:
    """Predict a galaxy/QSO redshift from a DESI spectrum in a .npz file.

    Use this first on any spectrum. `z_pred_map` is the official prediction
    (v2.1 classification head); `z_confidence` in [0, 1] flags likely
    catastrophic outliers below ~0.3 — verify those with
    identify_spectral_lines before trusting them. Deterministic; the first
    call loads the model checkpoint and can take extra seconds.
    """
    return tools.predict_redshift_impl(npz_path)


@mcp.tool()
def identify_spectral_lines(npz_path: str, z: float) -> dict:
    """Physically test a redshift hypothesis against the spectrum's peaks.

    Use it to validate any z — the model's, the user's or your own: known
    rest-frame lines shifted by (1+z) are matched to detected emission peaks,
    giving `match_fraction` and a verdict ('consistent' at >= 0.4). It also
    reports `n_peaks_detected` and `strongest_peaks_angstrom` (top 5 by
    prominence), so when a z fails you can derive alternative hypotheses by
    assuming the strongest peak is Hα, [OII] or Lyα and re-test each one.
    Needs no model. Caveat: a weak verdict is lack of confirmation, not
    refutation — absorption-dominated spectra match poorly even at the true z.
    """
    return tools.identify_spectral_lines_impl(npz_path, z)


@mcp.tool()
def reconstruct_spectrum(npz_path: str, mask_ratio: float = 0.5) -> dict:
    """Probe prediction stability by masking part of the spectrum.

    Use it as a robustness check once you have a candidate z: a random
    `mask_ratio` fraction of the model's 273 tokens is hidden and the
    redshift re-predicted. If `z_pred_under_masking` stays close to the
    full-spectrum z, the prediction does not hinge on a single feature;
    large swings mean fragile evidence.
    """
    return tools.reconstruct_spectrum_impl(npz_path, mask_ratio)


if __name__ == "__main__":
    mcp.run()  # stdio transport
