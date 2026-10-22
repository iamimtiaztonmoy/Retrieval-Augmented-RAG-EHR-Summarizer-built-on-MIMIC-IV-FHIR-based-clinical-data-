# Encounter Evidence Summarizer

A local LLM research pipeline for **query-focused, retrospective encounter summarization** using selected tables from full **MIMIC-IV 3.1**, with optional radiology reports from **MIMIC-IV-Note 2.2**. Each generated claim must cite retrieved evidence with an exact quotation. An extractive baseline runs without a model.

**Status:** synthetic software validation only. Full MIMIC ingestion, real-model generation, clinical quality, and full-dataset throughput have **not** been validated. This is not clinical decision support. It does not train or fine-tune an LLM. The original FHIR/TF-IDF demo is retained as a legacy baseline.

## Prerequisites and data access

- Python **3.12**, pip, and SQLite with **FTS5** enabled. Linux/POSIX commands below were tested with Python 3.12.14.
- Full structured data: [MIMIC-IV 3.1 on PhysioNet](https://physionet.org/content/mimiciv/3.1/), DOI [10.13026/kpb9-mt58](https://doi.org/10.13026/kpb9-mt58).
- Optional text: [MIMIC-IV-Note 2.2](https://physionet.org/content/mimic-iv-note/2.2/), DOI [10.13026/1n74-ne17](https://doi.org/10.13026/1n74-ne17). This is a separate resource with its own access requirements; the core release alone does not supply these notes.
- These are **deidentified clinical records, not wholly synthetic data**. Access requires PhysioNet credentialing, required CITI training, and signing each project's data-use agreement. Obtain files through the official pages in an authorized environment. Do not upload them into this repository or this chat.
- For generation: a locally installed Ollama server and approved local model weights. No model download or inference is performed by default. See [local inference and data use](docs/data-access.md).

The software reads these extracted files as CSV or gzip CSV; `--hosp` points directly at `hosp/` and `--notes` directly at the directory containing `radiology.csv.gz`:

| Input | Required | Purpose |
| --- | --- | --- |
| `hosp/admissions.csv[.gz]` | Yes | Patient/admission scope and retrospective time interval |
| `hosp/diagnoses_icd.csv[.gz]` + `d_icd_diagnoses.csv[.gz]` | Yes | Retrospective billing diagnoses and labels |
| `hosp/labevents.csv[.gz]` + `d_labitems.csv[.gz]` | With `--labs` | Laboratory values, units, chart/store times |
| `hosp/prescriptions.csv[.gz]` | With `--prescriptions` | Prescription orders; not proof of administration |
| `radiology.csv[.gz]` | With `--notes` | Radiology text with source and availability times |

**Discharge notes are never indexed.** ICU chart events, procedures, EMAR and other tables are not yet supported. The adapters target selected full-release tables, not every module. Note/core version overlap must be measured locally; joins require both `subject_id` and `hadm_id`, and unlinked rows are counted and excluded.

## Installation

```bash
git clone https://github.com/iamimtiaztonmoy/Retrieval-Augmented-RAG-EHR-Summarizer-built-on-MIMIC-IV-FHIR-based-clinical-data-.git ehr-summarizer
cd ehr-summarizer
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pytest -q
```

`requirements-lock.txt` records the complete resolved Python environment used for validation; `requirements.txt` and `requirements-dev.txt` declare the pinned direct dependencies. SQLite is provided by Python/the OS and its version is recorded in index manifests. Ollama, model weights, and their licenses are separate; no GPU is required for the extractive demo. Model hardware requirements depend on the chosen weights, quantization and context window.

## Run the reproducible synthetic example

All files in `tests/fixtures/` are newly authored fictional examples, not samples copied from MIMIC. Run commands from the repository root:

```bash
python -m clinical_rag ingest \
  --hosp tests/fixtures/hosp --notes tests/fixtures/note \
  --labs --prescriptions --synthetic --db artifacts/synthetic.sqlite

python -m clinical_rag summarize \
  --db artifacts/synthetic.sqlite --subject-id syn-001 --hadm-id adm-001 \
  --query 'opacity' --backend extractive --out artifacts/summary.json

python -m clinical_rag evaluate \
  --db artifacts/synthetic.sqlite --cases tests/fixtures/cases.jsonl \
  --split all --out artifacts/evaluation.json
```

Ingestion refuses to overwrite an existing index. Use a new database path to repeat a run. Outputs default to private file permissions. `artifacts/`, local labels and source data are ignored by Git. The CLI requires an explicit output file for retrieval, generation and evaluation; it does not print patient text to the console.

### Verified synthetic output

Captured synthetic output is in [examples/synthetic-summary.json](examples/synthetic-summary.json) and [examples/synthetic-evaluation.json](examples/synthetic-evaluation.json). The extractive summary preserves this entire source text:

```text
Chest radiograph: right lower lobe opacity. No pleural effusion.
```

The five authored retrieval cases include three positive cases and two negative/scope-isolation cases. The captured fixture run obtains source Recall@6 = 1.0, source MRR@6 = 1.0 and negative retrieval abstention = 1.0. These are **tiny software checks**, not clinical performance estimates or real LLM results. A live local API capture is in [examples/synthetic-api.json](examples/synthetic-api.json). The LLM HTTP protocol is tested with mocked responses and a loopback HTTP stub; no installed model was available in the validation environment.

## Run with authorized full data

After completing official access requirements and downloading files locally:

```bash
python -m clinical_rag ingest \
  --hosp /secure/mimiciv/3.1/hosp \
  --notes /secure/mimic-iv-note/2.2/note \
  --labs --prescriptions --db /secure/runs/encounters.sqlite
```

Omit `--notes`, `--labs`, or `--prescriptions` if those sources are not part of your study. Use `--subjects /secure/cohort-subjects.txt` to limit ingestion to one subject ID per line. Do not mark real data `--synthetic`. The index stores input file SHA-256 hashes, file sizes, version declarations, selection, row inclusion/exclusion counts, Python/SQLite versions and chunk settings. Large event tables stream; admission and dictionary maps remain in memory. Full-cohort RAM, index size and latency are unmeasured. Begin with a defined pilot cohort.

### Local LLM generation

Install Ollama separately. Acquire and review an appropriate local model before handling restricted data; record its license, model card, digest and quantization. Start the server in local-only mode, with the cloud features disabled:

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Then in another shell, set a model name already installed locally:

```bash
export RAG_MODEL='your-approved-local-model:tag'
python -m clinical_rag summarize \
  --db /secure/runs/encounters.sqlite \
  --subject-id YOUR_SUBJECT_ID --hadm-id YOUR_HADM_ID \
  --query 'Summarize documented pneumonia findings and laboratory results' \
  --backend ollama --model "$RAG_MODEL" --out /secure/runs/summary.json
```

The adapter uses Ollama `/api/tags` and `/api/chat`, only over a literal loopback IP. HTTP redirects and environment proxies are disabled; model names containing `cloud` are rejected. The server must still be configured and audited for offline local inference; a loopback URL alone does not prove where an external server executes a model. No cloud provider or arbitrary remote endpoint is supported. See the [Ollama FAQ](https://docs.ollama.com/faq) and [chat API](https://docs.ollama.com/api/chat).

Generation uses temperature 0, seed 42, 8,192 context tokens, a 2,048 output-token request, and a 12,000-character evidence budget. Whole chunks are included until the budget is exhausted. Character limits do not guarantee token fit for every model/language. The output records the model digest and parameters, prompt version/hash and evidence IDs. These settings improve traceability but do not guarantee bit-identical generation across hardware/runtime versions. Record `ollama --version`, hardware, quantization and timing with your experiment.

## Retrieval and generation behavior

1. Stream selected CSV tables and map records to **both** patient and admission. Diagnoses are explicitly labeled retrospective billing information, not onset dates.
2. Lab and radiology evidence must have valid event and storage times, event time within the admission and storage time no later than discharge. Missing times and unsupported/unlinked rows are excluded and counted. Prescription start time must lie within the encounter, but prescription availability time is not established by this table; this is a retrospective task, not early prediction.
3. Split text into 1,200-character chunks with 150-character overlap and content-derived SHA-256 IDs. Keep source table/note ID and event time. No discharge-summary target is read.
4. Use disk-backed SQLite FTS5 BM25 lexical retrieval. Patient/admission predicates apply before the limit. Query terms are quoted and OR-combined, capped at 64 unique alphanumeric tokens. Default `top_k=6`; valid range 1–20. No token overlap returns no evidence, rather than zero-score fallback documents. Ties sort by chunk ID. FTS BM25 ranks are lower-is-better, corpus-dependent values, not probabilities. Corpus-wide statistics can affect within-encounter ranking.
5. Send retrieved evidence to the local LLM or return the extractive baseline. The prompt treats source text as untrusted data, asks for negation/uncertainty preservation, and has no tools.
6. Reject invalid schema, invented/out-of-context IDs, empty citations, and quotes that are not exact source substrings of at least eight non-whitespace characters. Fail closed to abstention on those errors.

**Citation presence and exact quotation do not prove that a claim is entailed by the quote.** A model can cite a real sentence while misinterpreting it. Clinical entailment, completeness, negation and safety require independent review. A lexical match also does not prove that a question is answerable. Empty retrieval produces abstention; the LLM may also abstain; the extractive baseline simply returns matching evidence.

## API contract

This release **replaces the previous `GET /summary` API** with scoped POST endpoints; old clients must migrate. The legacy FHIR demo remains runnable via `demo.py` but is not served by the new API.

```bash
export RAG_DB=artifacts/synthetic.sqlite
export RAG_BACKEND=extractive
export RAG_API_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another shell with the same token:

```bash
curl --fail-with-body http://127.0.0.1:8000/v1/summarize \
  -H "Authorization: Bearer $RAG_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"subject_id":"syn-001","hadm_id":"adm-001","query":"opacity","top_k":6}'
```

| Route | Authentication | Contract |
| --- | --- | --- |
| `GET /health` | None | Liveness only: `{"status":"ok","clinical_validation":false}` |
| `GET /ready` | Bearer token | Checks nonempty index and FTS query; returns status/chunk count; does not check model readiness |
| `POST /v1/retrieve` | Bearer token | Required `subject_id`, `hadm_id`, `query` strings; optional `top_k` 1–20; returns `evidence` array and `abstained` boolean |
| `POST /v1/summarize` | Bearer token | Same inputs; returns `abstained`, `claims`, `reason`, `backend`, `prompt_version`, `prompt_sha256`, `evidence_ids`, `model`, and included `evidence` |

`claims` is an array of `{text, citations:[{chunk_id, quote}]}`. Evidence objects contain `id`, `subject_id`, `hadm_id`, `source`, `source_id`, `event_time`, `text`, `rank`. Model metadata is null for abstention before validation, otherwise a backend-specific metadata object. No-match/unknown encounter yields HTTP 200 with empty evidence/claims and `abstained=true`. `reason` distinguishes missing evidence, model abstention and rejected model output.

Errors: 401 missing/incorrect token; 422 invalid body (including blank strings, extra fields, query >2,000 characters); 503 missing/invalid index, token configuration (<32 characters), or model configuration; 502 model transport failure. Invalid LLM schema/citations produce HTTP 200 with abstention and a reason, never unchecked generated text. Framework errors use `{"detail":...}` (string or validation-error array). Requests carry JSON bodies, not clinical text in URL query strings. `/docs` and `/openapi.json` describe request validation but do not establish clinical validity.

The bearer token grants access to the entire configured index, not a patient-specific entitlement. There is no per-user authorization, production TLS, audit service, rate limiter or multi-tenant isolation. Keep the service on loopback. It is a local research tool, not a deployed clinical application.

## Evaluation approach

`python -m clinical_rag evaluate` consumes local JSONL cases with `case_id`, `subject_id`, `hadm_id`, `query`, and `relevant_sources` (`source:source_id` strings). See [synthetic cases](tests/fixtures/cases.jsonl). Missing positive gold sources fail evaluation rather than silently scoring a different corpus. Empty gold lists label unanswerable cases.

Implemented metrics: source Recall@k, reciprocal rank and hit rate on positive cases; no-result abstention rate on negative cases. `k` counts retrieved chunks; source IDs are deduplicated before source-level scoring/rank calculation. This deduplicated MRR is not a standard chunk-rank MRR. Evaluation records corpus manifest, label-file hash, configuration and Git HEAD. With a dirty worktree Git HEAD alone is insufficient; run committed code.

Patient-level splits use SHA-256 of `seed:subject_id` (80/10/10 bucket allocation). All admissions of a patient share a split. Default evaluation is `--split test`; use validation for prompt/model decisions. `--split all` is appropriate for fixture checks, not a held-out clinical claim. No model is trained by this code. The legacy identifier-prefix accuracy check is not clinical retrieval evaluation.

[Research protocol](docs/research-protocol.md) defines baseline comparisons, leakage controls, clinical review, uncertainty estimates and subgroup analyses. **Those experiments have not been run.** No clinical labels, human summaries, ROUGE/BERTScore results, factuality scores or full-data performance numbers are fabricated here.

## Limitations and remaining evidence

- Synthetic fixtures validate software behavior, not robustness to all full-release records or clinical quality. Full-scale ingestion, local model inference and version overlap need authorized local validation.
- Retrospective billing diagnoses can encode post hoc knowledge. This pipeline must not be repurposed as an admission-time prediction model. Discharge notes remain excluded, but structured data can still overlap with a future reference summary.
- Lexical retrieval lacks embeddings, synonym resolution and learned reranking. Short context may omit crucial evidence. Clinical abbreviations, negation, conflicting records and prompt injection remain open challenges.
- Lab units are preserved verbatim, not converted or clinically interpreted. Prescription orders are not administrations. No age, severity, causal or discharge-medication inference is performed deterministically.
- File hashes identify inputs; they do not certify source authenticity or consent. Hashing reads entire files in a second pass and requires stable inputs during a run.
- Direct dependencies and a resolved lock are provided; model weights/runtime and dataset files are separately controlled. No real-data output is published.
- The code repository has no selected project license; dataset/model licenses are separate. A maintainer should explicitly choose a code license before downstream redistribution.

## Data-use guidance

Follow the [PhysioNet LLM guidance](https://physionet.org/news/post/llm-responsible-use/) and the agreements for every source. Locally deployed models are recommended there. Third-party services require verified data handling, including zero retention, no training and no human review; this project implements no such remote path. Deidentification does not remove data-use obligations. Derived text, indexes, labels and model artifacts may remain sensitive and must not be published to GitHub; PhysioNet describes controlled sharing under the source agreement.

Keep downloads, cohort IDs, prompts, responses, indexes and evaluation artifacts in approved private storage outside the repository or ignored folders. `.gitignore` is a convenience, not an access control or a guarantee against forced commits. Synthetic examples are the only new record-level artifacts intended for publication. See [data access and governance](docs/data-access.md).

## Project layout and legacy demo

- `clinical_rag/`: ingestion, SQLite retrieval, local LLM generation, label-based evaluation and CLI.
- `api/main.py`: scoped, authenticated local API.
- `tests/fixtures/`: authored fictional CSVs and retrieval labels; `tests/test_pipeline.py`: tests.
- `examples/`: captured synthetic baseline outputs.
- `docs/`: access instructions, protocol, validation record and prioritized remaining work.
- `src/`, `demo.py`, `data/patient_summaries.csv`: original FHIR demo and stored demo summaries.

To run the old parser: set `FHIR_DIR` to the FHIR demo's directory containing `MimicPatient.ndjson.gz` and `MimicCondition.ndjson.gz`, then run `python demo.py`. It overwrites the legacy CSV, generates gender/birthDate/condition templates, and prints a TF-IDF patient-ID-prefix smoke test. It does not calculate age or use an LLM. The full-data CSV pipeline above is separate; it does not treat full MIMIC as if it were the FHIR demo.
