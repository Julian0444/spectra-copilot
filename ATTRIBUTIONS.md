# Code and data attribution

The repository code is licensed under MIT; see [LICENSE](LICENSE).
This does not relicense third-party DESI data or imply DESI endorsement.

DESI EDR data are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Release citation: DESI Collaboration et al. (2024), *The Early Data Release
of the Dark Energy Spectroscopic Instrument*, AJ 168, 58,
[doi:10.3847/1538-3881/ad3217](https://doi.org/10.3847/1538-3881/ad3217).
The source used here is the `edr_sv3` subset of
[Multimodal Universe](https://github.com/MultimodalUniverse/MultimodalUniverse).

Modification notice: this project selects spectra/labels, exports examples as
NPZ, and derives normalized, interpolated arrays, masked reconstructions,
predictions and embeddings. These are project products, not DESI pipeline
releases. Real examples retain DESI flux, wavelengths, inverse variance,
bad-pixel masks and catalog redshift after array-format conversion; the
single-line trap in Copilot is synthetic. Code MIT does not replace data
attribution when those examples or derived products are redistributed.

## Required DESI acknowledgment

The following reusable acknowledgment is reproduced as requested by
[DESI Data License and Acknowledgments](https://data.desi.lbl.gov/doc/acknowledgments/)
(checked 2026-10-09). Include this file with redistributed examples/derived data
and carry the acknowledgment into the model card and Space publication.

This research used data obtained with the Dark Energy Spectroscopic Instrument (DESI).
DESI construction and operations is managed by the Lawrence Berkeley National Laboratory.
This material is based upon work supported by the U.S. Department of Energy, Office of Science, Office of High-Energy Physics, under Contract No. DE–AC02–05CH11231, and by the National Energy Research Scientific Computing Center, a DOE Office of Science User Facility under the same contract.
Additional support for DESI was provided by the U.S. National Science Foundation (NSF), Division of Astronomical Sciences under Contract No. AST-0950945 to the NSF’s National Optical-Infrared Astronomy Research Laboratory;
the Science and Technology Facilities Council of the United Kingdom;
the Gordon and Betty Moore Foundation;
the Heising-Simons Foundation;
the French Alternative Energies and Atomic Energy Commission (CEA);
the National Council of Humanities, Science and Technology of Mexico (CONAHCYT);
the Ministry of Science and Innovation of Spain (MICINN),
and by the DESI Member Institutions: www.desi.lbl.gov/collaborating-institutions.
The DESI collaboration is honored to be permitted to conduct scientific research on I’oligam Du’ag (Kitt Peak), a mountain with particular significance to the Tohono O’odham Nation. Any opinions, findings, and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the U.S. National Science Foundation, the U.S. Department of Energy, or any of the listed funding agencies.
