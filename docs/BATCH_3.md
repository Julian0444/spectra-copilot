# Batch 3: shared local data infrastructure

This original checkout is on `codex/lote-3` from the delivered batch-2 HEAD.
The two batch-2 review fixes are local commits: provenance outside the resolved
opaque directory, and verified immutable Hub assets. No historical derivatives,
index, weights, cases, CSVs or transcripts were regenerated.

Data and scientific evaluation live in the FM original:
`<fm-repo>`, `codex/lote-3`.
Use the two source revisions together; the old 0.2.0 wheels still describe their
old bytes. No wheels were rebuilt, and their old acceptance manifests were not
reused as evidence for batch 3.

The raw snapshot is
`<local-home>/.local/share/spectra-data/933b9056b93b0f3e7790ee28c43412b49c39e232/`.
Its seven parquet are size/SHA-256 checked and read-only. The object-ID index is
`<local-home>/.local/share/spectra-data/derived-933b9056/spectra-input-v2.sqlite`.
IDs remain strings, including values above the exact integer range of float64.
`desi_fm.local_data.LocalDESIStore.rows_for_ids` preserves caller order, rejects
duplicate/missing requested IDs and binds the index to its snapshot hash.
`raw` checks the requested ID against the actual parquet row.

The selection and export-ID checks are in FM `docs/evidence/batch3-historical-ids*`.
All 150 preserved Copilot cases match those reconstructed IDs and their raw
arrays/preprocessing. Labels remain evaluator data; this does not authorize
sending the selection manifest, warning flags or source paths to the LLM.
Persistent scientific input derivation continues through
`scripts/derive_agent_inputs.py`, with its provenance outside the opaque folder.

Complete scientific runs and the offline repeat are separate new destinations
outside both repositories. The comparison uses v1 scalar/v2.1 MAP plus secondary
outputs and separately fixed-mask reconstruction. These remain historical,
non-independent diagnostics. No paid LLM was used. The historical FAISS index
was preserved, and its generation encoder/preprocessing provenance remains
unknown; this batch does not certify its scientific compatibility.

For lot 4 preparation, consume the verified raw snapshot and ID index; resolve
observation grouping limits, create new ID splits and use fresh weights according
to the consensus. No new split/test was created or opened here. Lot 5 continues
to require a separate blind agent evaluation and a budget. Credential revocation
and publication remain unverified/pending.
