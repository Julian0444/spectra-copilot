# Batch 2: contracts, inference and installed resources

This batch changes software contracts. It does not train or establish improved
scientific accuracy. Historical evaluations, examples and transcripts are intact.
The matcher score/tolerance, hypothesis arithmetic and final override policy
remain experimental and belong to batch 5.

Scientific inputs follow FM `docs/INPUT_CONTRACT.md`: real rectangular arrays,
explicit bad flags/positive finite ivar, ordered together, internal gaps invalid,
8 usable raw samples and 8 supported model pixels. These numerical prerequisites
are not calibrated quality cuts. Single-spectrum tools/Gradio reject multirow
files; batch Python/CLI/REST support exactly shared `(P,)` grids/quality fields.
Legacy files declare Angstrom by contract; explicit nm converts by 10.
Predictions include coverage, config and checkpoint SHA-256/step. The matcher now
uses shared validity and sorts arrays, retaining its historical peak heuristic;
this is not a calibrated scientific matcher. Similarity rejects unusable input
before searching and rejects invalid embeddings/index IDs.

Classifier facts: configured endpoints, decoded bin centers and a sample's
observed maximum are different. `z_pred=expm1(E[log(1+z)])` and MAP come from the
same posterior, with no second regression head. `z_confidence=1-H(p)/log(n_bins)`
is concentration, not calibrated probability of correctness. Actual config and
identity are included in the system prompt; observed_max is unknown there.

Each agent run derives a separate temporary `spectrum.npz` under an opaque temp
directory. It includes only flux/wavelength/ivar/mask/unit, stripping object IDs,
labels and all other metadata. Original paths never appear in messages or tool
schemas. The runner restricts file tools to this alias. Source/derived SHA-256
and protocol `opaque-scientific-input-v2` are returned to the evaluator; human
transcript runs save a separate `.input.json` provenance record. Original files
are never rewritten. The fictional prompt example does not solve case_000.

State is per execution. At most six analysis tool calls can execute; at most
eight SDK iterations are permitted. A validated submit_report can be recorded
once; later submissions/tools are rejected without replacing it. Structured
reports accept finite nonnegative z, high/medium/low confidence, 0..15 integer
lines and nonempty summary. These domains do not establish scientific correctness
or abstention policy. Multiple submits and consecutive runs are tested with a
simulated LLM client. No paid API calls are needed for acceptance.

`k`: integer 1..100 for neighbors (capped to a smaller existing index), 1..30 for
references. `mask_ratio`: finite real in [0,0.9]. Line hypotheses: finite z>=0;
no classifier ceiling is imposed on hypotheses. Invalid argument types, including
boolean numbers, are rejected. MCP schemas expose the same ranges.

## Distribution and reproducibility

The installed corpus is `copilot/refs/`, read through `importlib.resources`.
The top-level `refs/` remains the preserved historical corpus. Its 16 original
files were copied; the current QSO note corrects the model-limit claim and
separates model configuration from survey facts. `rag.corpus_hashes()` and
`corpus_revision()` fingerprint installed bytes, independent of checkout paths.
`eval/run_evals.py` now fingerprints those resources instead of looking beside
the installed package. Manifest schema/protocol v2 preserves batch 1's atomic
writes, locks, compatible resume and full case map; old manifests cannot be
silently resumed under changed contracts/code/corpus.

Both local distributions are version 0.2.0. Copilot requires `desi-fm>=0.2,<0.3`
instead of a mutable Git URL. Before publishing these versions, use **both local
wheels**; no dependency points at an unpublished local Git commit. Build from
these batch-2 branches and install together, for example:

```sh
python -m pip wheel --no-deps --no-build-isolation /path/to/fm -w /path/to/wheels
python -m pip wheel --no-deps --no-build-isolation /path/to/copilot -w /path/to/wheels
python -m venv /path/to/isolated-env
/path/to/isolated-env/bin/python -m pip install --constraint /path/to/tested-dependencies.txt /path/to/wheels/desi_fm-0.2.0-py3-none-any.whl /path/to/wheels/spectra_copilot-0.2.0-py3-none-any.whl
cd /path/outside/checkouts
env -u PYTHONPATH /path/to/isolated-env/bin/python -c 'from copilot.rag import lookup_reference_impl; print(lookup_reference_impl("Halpha OII confusion"))'
```

The delivery manifest records actual wheel hashes, code revisions, installed
versions/import paths, checkpoint and corpus hashes and test commands. Exact
versions are evidence of what was tested, not a claim that all supported Python
versions were tested. Contract suites use small seeded models; real-weight smoke
is bounded and separate. UI hosting/ZeroGPU is simulated; deployment is pending.
The dataset revision is the historical reference from batch 1, not a newly
validated/downloaded corpus. Key revocation and publication remain pending.
