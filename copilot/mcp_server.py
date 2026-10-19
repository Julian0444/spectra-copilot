"""MCP server exposing the desi-fm multitask transformer as tools.

Any MCP client (Claude Code, Claude Desktop, the inspector, ...) gets the
same deterministic toolset the Claude-API agent uses: redshift prediction,
heuristic line comparison and masked reconstruction. The client's LLM does
the reasoning; these tools only report measurements.

Run standalone:  python -m copilot.mcp_server
Dev inspector:   mcp dev copilot/mcp_server.py

Set DESI_FM_CKPT to a local checkpoint path to skip the ~104 MB Hub download
on the first model call.
"""

from mcp.server.mcpserver import MCPServer
from typing import Annotated
from pydantic import Field
from mcp.types import CallToolResult, TextContent
from desi_fm.inputs import SpectrumInputError
import json

from copilot import rag, tools, __version__

mcp = MCPServer(
    "desi-fm",
    version=__version__,
    instructions=(
        "Tools around the desi-fm spectral multitask transformer (DESI galaxy/QSO "
        "spectra). Typical loop: predict_redshift first; if z_confidence is "
        "low (< 0.3) or the user asks for verification, test the redshift "
        "with identify_spectral_lines and derive alternative hypotheses from "
        "its strongest_peaks_angstrom; find_similar_spectra adds a "
        "descriptive signal from the same supervised encoder, not independent confirmation — neighbors whose catalog redshifts cluster "
        "around a candidate z support it; lookup_reference retrieves DESI "
        "reference notes (target-type z ranges, line degeneracies) to "
        "sanity-check a conclusion, citing sources by id. Inputs are .npz "
        "files containing 'flux' and 'wavelength' (Angstrom) arrays."
    ),
)


def _invoke(function, *args):
    """Return safe typed errors without exposing exception messages or traces.

    Only SpectrumInputError denotes bad scientific inputs/arguments (including
    unreadable input files, translated by read_npz). MCP/Pydantic validates the
    schema before this boundary. All other execution failures, including missing
    or unreadable assets, offline Hub cache misses and asset identity mismatches,
    are internal_error. Neither branch returns paths, secrets or raw exceptions.
    """
    try:
        return function(*args)
    except SpectrumInputError:
        error = {'error': {'code': 'invalid_input', 'type': 'SpectrumInputError'}}
    except Exception:
        error = {'error': {'code': 'internal_error', 'type': 'ServerExecutionError'}}
    return CallToolResult(is_error=True, structured_content=error,
                          content=[TextContent(type='text', text=json.dumps(error))])


@mcp.tool()
def predict_redshift(npz_path: str) -> dict:
    """Predict a galaxy/QSO redshift from a DESI spectrum in a .npz file.

    Use this first on any spectrum. `z_pred_map` is the official prediction
    (v2.1 classification head); `z_confidence` in [0, 1] is entropy-based concentration, not calibrated probability of accuracy.
    The configured and bin-center ranges are in model_identity. Use
    identify_spectral_lines for an experimental line check. Deterministic; the first
    call loads the model checkpoint and can take extra seconds.
    Invalid spectrum/arguments return invalid_input; unavailable or invalid server
    assets and other execution failures return internal_error, with is_error.
    """
    return _invoke(tools.predict_redshift_impl, npz_path)


@mcp.tool()
def identify_spectral_lines(npz_path: str, z: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]) -> dict:
    """Compare a redshift hypothesis heuristically with detected emission peaks.

    This does not physically confirm any z. For a supplied hypothesis, known
    rest-frame lines shifted by (1+z) are matched to detected emission peaks,
    giving `match_fraction` and a verdict ('consistent' at >= 0.4). It also
    reports `n_peaks_detected` and `strongest_peaks_angstrom` (top 5 by
    prominence), so when a z fails you can derive alternative hypotheses by
    assuming the strongest peak is Hα, [OII] or Lyα and re-test each one.
    Needs no model. Caveat: a weak verdict is lack of confirmation, not
    refutation — absorption-dominated spectra match poorly even at the true z.
    """
    return _invoke(tools.identify_spectral_lines_impl, npz_path, z)


@mcp.tool()
def reconstruct_spectrum(npz_path: str, mask_ratio: Annotated[float, Field(ge=0, le=.9, allow_inf_nan=False, strict=True)] = 0.5) -> dict:
    """Probe prediction stability by masking part of the spectrum.

    Use it as a robustness check once you have a candidate z: a random
    `mask_ratio` fraction of the model's 273 tokens is hidden and the
    redshift re-predicted. If `z_pred_under_masking` stays close to the
    full-spectrum z, that describes stability for this draw; it does not
    establish robustness or physical correctness.
    Invalid spectrum/arguments return invalid_input; unavailable or invalid server
    assets and other execution failures return internal_error, with is_error.
    """
    return _invoke(tools.reconstruct_spectrum_impl, npz_path, mask_ratio)


@mcp.tool()
def find_similar_spectra(npz_path: str, k: Annotated[int, Field(ge=1, le=100, strict=True)] = 5) -> dict:
    """Find the k most similar spectra in a 15k-spectrum DESI reference index.

    Use it as a descriptive comparison, not independent confirmation: the
    spectrum is embedded with the multitask transformer's encoder and matched by
    cosine similarity against 15k DESI training spectra, each neighbor
    reporting its catalog z. Neighbors whose redshifts cluster tightly around
    a candidate z support it; scattered neighbor redshifts add doubt. The
    signal comes from the embedding space, not the classification head — it
    shares the supervised encoder; historical index compatibility is unverified. The first call
    may download the index (~30 MB) from the Hub.
    Invalid spectrum/arguments return invalid_input; unavailable or invalid server
    assets and other execution failures return internal_error, with is_error.
    """
    return _invoke(tools.find_similar_spectra_impl, npz_path, k)


@mcp.tool()
def lookup_reference(query: str, k: Annotated[int, Field(ge=1, le=30, strict=True)] = 3) -> dict:
    """Consult the spectral-line catalog and DESI reference notes (BM25).

    Use it to sanity-check target-type vs redshift priors (BGS/LRG/ELG/QSO
    expected ranges), line visibility windows, and to explain classic line
    degeneracies (e.g. Halpha vs [OII] in single-line spectra). Returns up
    to k documents, strongest match first, each with an `id` to cite in
    square brackets, its public `source`, and a text snippet. The corpus is
    16 committed resources; queries with no term overlap return an
    empty list. Needs no model and runs offline.
    """
    return _invoke(rag.lookup_reference_impl, query, k)


if __name__ == "__main__":
    mcp.run()  # stdio transport
