# 0.3.0 — release notes

## Included software

- Explicit spectrum validity, masks, coverage, gaps and typed rejection.
- Official model redshift preserved in reports, with descriptive spectral
  measurements and bounded explanatory execution.
- FM Python inference, local Gradio interface and FastAPI service; Copilot CLI,
  five MCP tools, FAISS neighbors and local BM25 reference resources.
- Durable request accounting and SDK error metadata without secrets or content.
- Semantic-review inventory and citation checks, dispute worksheets and score
  provenance, with scientific judgments kept separate from mechanical checks.
- A public [reproduction guide](REPRODUCE.md), evaluation documentation and tests.

The default checkpoint remains v2.1; CNN-17 is experimental. No weights,
training protocol or scientific results change in this release. Install the
matching FM and Copilot tags; desi-fm is not on PyPI.

## Evaluation and limits

Mechanical acceptance passed on the single 128-case run: completion 127/128
(79/80 real, 48/48 synthetic), 126 calls, zero retries and US$0.1086672 certified
cost. The incomplete explanation remains in the denominator. Prediction
coverage was 122/128 requested; official model redshift was preserved on
122/122 eligible inputs. These checks do not establish scientific accuracy.

Both AI annotations are complete, with 894 claim disagreements and all 128 cases
pending human adjudication. Opus and Haiku share a provider. Scientific accuracy
and global acceptance remain pending; zero claim–citation pairs are not evidence
of full support. See the [evaluation](https://github.com/Julian0444/desi-spectra-fm/blob/v0.3.0/docs/EVALUATION.md) for protocols, historical
results and limitations. No improvement in redshift accuracy is claimed.

The public example is a historical functional demonstration, not a blind test.
The hosted application code is not updated by this release; its unpinned FM
dependency can change on a future rebuild. No installed hosted version is
asserted. The separate reproduction artifact bundle is not included in these
release assets.

## Wheel identities

| Wheel | SHA-256 |
|---|---|
| `desi_fm-0.3.0-py3-none-any.whl` | `5fe3eb7041a40901a22759e1d4e15fdfa6213ae5c93e3d16852cceb31979a011` |
| `spectra_copilot-0.3.0-py3-none-any.whl` | `ba05c2d178ab3de310f0c5da8d2cd759752db1fdbe8e25184c2285c6c875c102` |

Package executable files, configuration and resources are identical to the
wheels used for acceptance. Only README metadata and its RECORD entry change;
the evaluated wheels and evidence remain preserved. Tag installation remains
pending verification after publication.

Development and audits used AI coding assistants (Codex and Claude); decisions and verification records are in docs/.
