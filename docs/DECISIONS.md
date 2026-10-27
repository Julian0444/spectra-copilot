# Architecture and decisions

Copilot separates deterministic measurements, the official predictor and LLM
selection of recorded observations. The executor renders the report. Design
choices do not establish scientific performance; see the
[canonical evaluation](https://github.com/Julian0444/desi-spectra-fm/blob/main/docs/EVALUATION.md).

| Decision | Implemented choice | Alternative and reason or limit |
|---|---|---|
| Official redshift | Executor-owned `model_z` from default v2.1. | The historical agent replaced predictions and worsened the measured result. Generated alternatives cannot overwrite the official value. CNN-17 remains experimental. |
| Alternatives | Compute redshift candidates from measured wavelengths in code. | LLM arithmetic is not used as a measurement or as the official redshift. Single-line ambiguity remains explicit. |
| Evidence policy | Descriptive feature measurements with coverage and supported modalities. | The physical-confirmation development gate failed; confirmation verdicts are disabled. Absence outside coverage is not refutation. |
| Reporting | Protected template text tied to registered observations. | Free-form generated claims can be incompatible with measurements. Template fidelity still does not establish scientific truth. |
| Bootstrap | Obtain prediction and spectral measurements before LLM selection. | Mandatory evidence must not depend on whether the LLM happens to request it. All registered measurements inform minimum caution. |
| Neighbors | Cosine retrieval from FAISS embeddings of the same supervised encoder. | Neighbors are descriptive and not an independent physical validation. |
| References | Local deterministic BM25 over installed short technical notes. | Adding an embedding model would add a dependency; no measured retrieval comparison establishes superiority. ID membership is separate from semantic support. |
| Citation denominator | Count only emitted claim–citation pairs. | A retrieved excerpt and its own header are not a self-citation pair. Zero pairs are N/A and leave global acceptance pending. |
| API spending | Zero default budget, integer reservations, durable usage accounting and one-attempt phase records. | A key is not authorization. Unknown usage stops further work; failed attempts remain recorded. |
| Evaluation custody | Separate execution and scoring views; seal outputs and register externally before labels. | Labels must not steer reports, selections or post-opening changes. Public synthetic cases remain mechanism tests. |
| Semantic review | Two new blinded AI sessions; separately hashed annotations, validated join and human disputes. | AI agreement is not independent human review. Opus and Haiku share a provider. Julian adjudicates without overwriting original judgments. |
| Exposure | Five deterministic tools through Python/CLI and MCP; local UI separately. | The paid agent is optional and must be authorized explicitly. |

The reviewed implementation fixes inventory adjudication to registered disputes
and additions, preserving undisputed claims. It distinguishes actual annotation
disagreements from forced human review after loss of blindness and from changed
inventory. The [semantic procedure](BATCH_5C_AI_REVIEW.md) defines the contract;
[5C status](BATCH_5C_REPORT.md) records whether its execution gate has passed.

Development and audits used Codex and Claude. This records assistance and
technical decisions, not Julian's personal contribution; that account is H-18.
