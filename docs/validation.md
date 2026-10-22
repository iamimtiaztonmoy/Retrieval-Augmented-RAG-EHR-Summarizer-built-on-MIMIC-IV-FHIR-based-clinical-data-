# Validation record and prioritized next experiments

## Verified here (October 21, 2026)

- Python 3.12.14, Linux; SQLite 3.53.1 with FTS5. Exact Python packages are in `requirements-lock.txt`.
- Isolated virtual environment installation, `pip check`, module compilation and **20 passing tests**. One upstream TestClient deprecation warning remains.
- Live loopback Uvicorn HTTP checks: health/readiness/summarize/no-match return 200; missing authentication 401; invalid body 422. Captured fictional-data responses are in `examples/synthetic-api.json`.
- Synthetic ingestion: 3 admissions, 8 chunks/records; 3 billing diagnoses, 1 laboratory result, 1 prescription order and 3 radiology reports.
- Exclusions: 2 late/out-of-interval records, 1 missing-time record and 1 unlinked record.
- Positive retrieval labels: 3; negative labels: 2. Source Recall@6, deduplicated-source MRR@6 and negative retrieval abstention all 1.0 on these authored examples only.
- Tests exercise patient/admission scope, FTS query escaping, out-of-vocabulary abstention, gzip input, partial-index cleanup, refusal to overwrite, source hashes, stable chunks, exact-quote and citation-ID checks, strict response schema, token protection, API request validation and data/model failure paths.
- Local LLM API protocol verified with mocked replies and a real loopback HTTP stub. A stub is not model inference.
- Captured synthetic CLI outputs are under `examples/`. Their `git_commit` may say `unavailable` because capture preceded the first implementation commit; source hashes and prompt hashes are present. Re-run from the committed branch to record that commit. These examples are evidence of the documented fixture behavior, not a full experiment manifest.

No full restricted data, credentials, model weights, real patient-level labels or generated MIMIC content were accessed or added. The pre-existing demo CSV remains a legacy artifact and is not input to the new pipeline.

## Not verified

- End-to-end ingestion of MIMIC-IV 3.1 and Note 2.2; header/data irregularities and actual join coverage.
- Full-data throughput, disk/RAM budgets, retrieval latency and crash recovery.
- An installed Ollama release/model with real generation, its hardware behavior, truncation, factuality or clinical usefulness.
- Independent clinician relevance/summary labels, clinical outcome benefit, external validity, subgroup fairness, confidence intervals or model comparisons.
- Hosted CI success: the workflow is provided; local tests do not imply GitHub Actions ran successfully.

## Prioritized plan

| Priority | Deliverable | Completion evidence |
| --- | --- | --- |
| P0 | Authorized source access and pilot cohort | Official approvals/terms satisfied locally; version and file checksums; cohort definition; header/join/missingness audit |
| P0 | Approved local model installation | License/model card/digest, quantization, offline server configuration, runtime/hardware record; synthetic real-model output passing schema/citation checks |
| P0 | Full-data pilot | New private index; source counts/exclusions and spot checks against original rows; inspect medication/order and temporal semantics |
| P1 | Clinician-authored retrieval benchmark | Independent queries and source relevance labels, negative cases; fixed patient split, label hash and blinded review |
| P1 | Comparative clinical generation study | Freeze configuration; baseline/LLM runs; atomic claim/coverage review, disagreement resolution and patient-cluster uncertainty estimates |
| P1 | Scale assessment | Private resource/latency logs; batch/partition strategy as needed; FTS and ingestion failure recovery analysis |
| P2 | Retrieval and robustness experiments | Dense/hybrid and source-budget ablations, negation/uncertainty adversarial cases, prompt injection and context truncation analysis |
| P2 | Publication and release | Approved aggregate report, chosen project code license, reproducible committed configuration, controlled derivative sharing |

## API migration

`GET /summary` from the original demo is removed from `api.main:app`. Use `POST /v1/retrieve` or `POST /v1/summarize`, provide both scope identifiers and a bearer token. The old parser and TF-IDF classes remain available for legacy demonstrations. This is an intentional breaking API change, not a compatible patch.
