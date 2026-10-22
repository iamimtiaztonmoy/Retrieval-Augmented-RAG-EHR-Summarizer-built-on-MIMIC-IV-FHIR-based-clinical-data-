# Validation record and prioritized next experiments

## Verified here (updated October 22, 2026 UTC)

- Python 3.12.14, Linux; SQLite 3.53.1 with FTS5. Exact Python packages are in `requirements-lock.txt`.
- Isolated virtual environment installation, `pip check`, module compilation and **23 passing tests**. One upstream TestClient deprecation warning remains.
- Live loopback Uvicorn HTTP checks: health/readiness/summarize/no-match return 200; missing authentication 401; invalid body 422. Captured fictional-data responses are in `examples/synthetic-api.json`.
- Synthetic ingestion: 3 admissions, 8 chunks/records; 3 billing diagnoses, 1 laboratory result, 1 prescription order and 3 radiology reports.
- Exclusions: 2 late/out-of-interval records, 1 missing-time record and 1 unlinked record.
- Positive retrieval labels: 3; negative labels: 2. Source Recall@6, deduplicated-source MRR@6 and negative retrieval abstention all 1.0 on these authored examples only.
- Tests exercise patient/admission scope, FTS query escaping, out-of-vocabulary abstention, gzip input, partial-index cleanup, refusal to overwrite, source hashes, stable chunks, exact-quote and citation-ID checks, strict response schema, token protection, API request validation and data/model failure paths.
- Local LLM API protocol verified with mocked replies and a real loopback HTTP stub. A stub is not model inference.
- Captured synthetic CLI outputs are under `examples/`. Their `git_commit` may say `unavailable` because capture preceded the first implementation commit; source hashes and prompt hashes are present. Re-run from the committed branch to record that commit. These examples are evidence of the documented fixture behavior, not a full experiment manifest.

No full restricted data, credentials, real patient-level labels or generated MIMIC content were added. Public model weights were downloaded for fictional-fixture tests and kept outside the repository. The pre-existing demo CSV remains a legacy artifact and is not input to the new pipeline.

GitHub Actions also passed the locked install, tests, synthetic ingestion and evaluation for implementation commit `840ed6bbdf57ab4d44e33b6337d5f167b532aabb`: [CI run](https://github.com/iamimtiaztonmoy/Retrieval-Augmented-RAG-EHR-Summarizer-built-on-MIMIC-IV-FHIR-based-clinical-data-/actions/runs/39714152457).

## Real local-model fixture audit (October 22, 2026 UTC)

Ollama 0.40.8 ran with `OLLAMA_NO_CLOUD=1`, bound to `127.0.0.1`, using CPU inference. Prompt `encounter-evidence-v1`, temperature 0, seed 42, context 8192 and output limit 2048 were held fixed. Both Qwen2.5 instruct variants used Q4_K_M weights. No restricted patient record was used. Five cases comprise three answerable fixtures and two no-evidence cases; the latter bypass generation.

| Backend | Accepted answers | No-evidence abstentions | Rejected outputs | Transport failures | Mean seconds/case |
| --- | ---: | ---: | ---: | ---: | ---: |
| Extractive | 3 | 2 | 0 | 0 | 0.0000584 |
| Qwen2.5 0.5B instruct | 0 | 2 | 3 | 0 | 1.1894 |
| Qwen2.5 1.5B instruct | 2 | 2 | 1 | 0 | 3.7513 |

These are single-run integration observations, not statistical estimates or model-quality rankings. The 1.5B run was added after observing 0.5B failures; this is exploratory fixture testing, not held-out model selection. Timing includes loading and no-generation cases. CPU peak memory and hardware throughput were not benchmarked.

The 1.5B creatinine answer was “The patient's creatinine level was recorded as 1.2 mg/dL.” with an exact lab citation. Its accepted opacity answer was only “opacity”: mechanical validation does not enforce a useful or complete synopsis. A diagnostic repeat of the 0.5B opacity case returned contradictory abstention/claims and copied placeholder citation values; validation rejected it. Validation rules were not relaxed to improve these counts.

Complete fictional case outputs, model digests, usage and source hashes:
- [Extractive](../examples/synthetic-extractive-benchmark.json)
- [0.5B model](../examples/synthetic-llm-benchmark.json)
- [1.5B model](../examples/synthetic-llm-1.5b-benchmark.json)

See [reproduction commands and metric definitions](batch-benchmark.md). All recorded package source hashes were checked against the final implementation. Git was uncommitted during capture, which is explicitly recorded. The new benchmark has regression tests for retained transport failures, rejected citations and model identity; API success responses are typed in OpenAPI.

## Not verified

- End-to-end ingestion of MIMIC-IV 3.1 and Note 2.2; header/data irregularities and actual join coverage.
- Full-data throughput, disk/RAM budgets, retrieval latency and crash recovery.
- Clinical model usefulness, factuality and truncation behavior on realistic long records. Small-fixture CPU inference is now exercised; it does not resolve these gaps.
- Independent clinician relevance/summary labels, clinical outcome benefit, external validity, subgroup fairness, confidence intervals or model comparisons.
- Clinical validation is still absent even when automated CI passes.

## Prioritized plan

| Priority | Deliverable | Completion evidence |
| --- | --- | --- |
| P0 | Authorized source access and pilot cohort | Official approvals/terms satisfied locally; version and file checksums; cohort definition; header/join/missingness audit |
| P0 | Study model qualification (fixture installation completed) | License/model card/digest, quantization, offline server configuration, runtime/hardware record; synthetic real-model output passing schema/citation checks |
| P0 | Full-data pilot | New private index; source counts/exclusions and spot checks against original rows; inspect medication/order and temporal semantics |
| P1 | Clinician-authored retrieval benchmark | Independent queries and source relevance labels, negative cases; fixed patient split, label hash and blinded review |
| P1 | Comparative clinical generation study | Freeze configuration; baseline/LLM runs; atomic claim/coverage review, disagreement resolution and patient-cluster uncertainty estimates |
| P1 | Scale assessment | Private resource/latency logs; batch/partition strategy as needed; FTS and ingestion failure recovery analysis |
| P2 | Retrieval and robustness experiments | Dense/hybrid and source-budget ablations, negation/uncertainty adversarial cases, prompt injection and context truncation analysis |
| P2 | Publication and release | Approved aggregate report, chosen project code license, reproducible committed configuration, controlled derivative sharing |

## API migration

`GET /summary` from the original demo is removed from `api.main:app`. Use `POST /v1/retrieve` or `POST /v1/summarize`, provide both scope identifiers and a bearer token. The old parser and TF-IDF classes remain available for legacy demonstrations. This is an intentional breaking API change, not a compatible patch.
