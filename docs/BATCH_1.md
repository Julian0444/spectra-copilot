# Batch 1 — local execution record

Prepared 2026-10-09 (America/Los_Angeles), starting at
`52de8ec7629e9f636f600e56f01fa01bfe05a077`, branch `codex/lote-1`.
Initial `README.md` and `eval/README.md` edits were backed up privately, reviewed
and reconciled rather than staged as an unexplained working-tree snapshot.
Their initial/current hashes are in [local-edits.json](evidence/local-edits.json).
The final commit IDs and private preservation location are in the official
consensus execution table maintained beside both repositories.

## Evaluator

B11 reproduced before fixing: three cases existed; retrying the first left
only one row in the CSV while the summary reported three. The current runner
owns a complete map, unique mode-specific destination, immutable identity
manifest and atomic CSV replacement, with a final flush and disk-based summary.
It retains pending/error rows and retries them, skips completed baseline rows,
rejects incompatible inputs/mode/model/code/assets, and locks concurrent writers.
Historical CSVs cannot be silently adopted or overwritten. See
[eval/README.md](../eval/README.md) for the CLI and interruption/cost limits.

The source of scientific facts, prompts, label clues, input contracts and wheel
corpus packaging are unchanged; these belong to later batches. No new agent
benchmark or paid request was made.

## Evidence and presentation

[historical-assets.json](evidence/historical-assets.json) identifies 169
unchanged local results, inputs, examples and index assets by relative path,
size and SHA-256. Large assets remain in place and ignored; an inventory is
not a second physical backup. The model repository's
`scripts/check_historical_evidence.py` rechecks both inventories and recalculates
the stored comparison: 139/150 model successes, 119/150 agent, 21 broken,
1 recovered, retrospective hybrid 135/150. Confidence ranks historical risk;
it is not calibrated success probability. Both trap outcomes remain visible,
with different toolsets explicitly distinguished.

Readme corrections preserve the user's earlier distinction between report and
structured-run historical costs, the different toolsets, and the hybrid's
failure to recover outliers. They add the lineage/masking limitations and remove
unsupported physical-verification, UMAP-only-pretraining and catastrophic-error
claims. This is prepared local content; no remote publication was performed.

## License, credentials and follow-up

The owner explicitly selected MIT, copyright Julian Irusta Roure, on 2026-10-09.
[LICENSE](../LICENSE) covers code; [ATTRIBUTIONS.md](../ATTRIBUTIONS.md) covers
DESI EDR citation, data CC BY 4.0, transformations and required acknowledgment.
It must accompany redistributed examples/derived products.

Credential revocation/consumer rotation was not verified. The account owner
must revoke the historical Anthropic key and the key shared in this session,
replace affected consumers securely and report only date/status. No key from
this session was used or stored. Publication remains pending after review;
model-repository `docs/PUBLICATION.md` contains the prepared About/portfolio
text and Hub/Space file mapping.
