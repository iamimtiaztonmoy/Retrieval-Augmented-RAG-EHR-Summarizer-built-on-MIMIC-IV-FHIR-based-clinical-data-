# Reproduce a batch generation audit

This audits retrieval, generation completion, citation/schema rejection and latency on the same cases. It does **not** score clinical correctness, citation entailment or information coverage. A high answer rate can coexist with incorrect claims.

## Fixture run

Install `requirements-lock.txt`, then create the synthetic index using the README quick start. From the repository root:

```bash
python -m clinical_rag benchmark --db artifacts/synthetic.sqlite \
  --cases tests/fixtures/cases.jsonl --split all --backend extractive \
  --out artifacts/extractive-benchmark.json
```

For real local inference, install [Ollama from its official distribution](https://docs.ollama.com/linux). In a separate terminal start the server:

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Download an explicitly chosen model while online, before loading any restricted data. The small models below are integration probes, not selected or approved clinical models:

```bash
ollama pull qwen2.5:0.5b-instruct
ollama pull qwen2.5:1.5b-instruct
python -m clinical_rag benchmark --db artifacts/synthetic.sqlite \
  --cases tests/fixtures/cases.jsonl --split all --backend ollama \
  --model qwen2.5:1.5b-instruct --out artifacts/llm-benchmark.json
```

The captured run used Ollama **0.40.8**, CPU inference, Python 3.12.14 and SQLite 3.53.1. Both [0.5B](https://ollama.com/library/qwen2.5:0.5b-instruct) and [1.5B](https://ollama.com/library/qwen2.5:1.5b-instruct) registry entries identify Q4_K_M quantization and Apache-2.0 model licensing. The repository's code license is a separate unresolved maintainer decision. Model tags are mutable: compare the complete digest in the output before claiming reproduction. No weights are committed.

## Output interpretation

- `answered`: schema and exact-quote checks accepted nonempty claims. This does not establish entailment.
- `abstained`: no evidence or model-declared insufficient evidence.
- `validation_failure`: model response or citation/schema rejected; unsafe raw text is not saved.
- `transport_failure`: local connection or timeout failed. The case remains in the denominator; raw exception text is not saved.

`status_counts` always totals the number of selected cases. `answered_fraction` uses all selected cases. Negative cases may bypass model inference entirely. `mean_elapsed_seconds` includes those fast no-evidence cases and initial model loading, and measures retrieval plus generation/validation, not ingestion or downloads. Ollama `usage` records available token counts and duration fields in nanoseconds. Small-fixture latency is not a throughput or clinical-performance benchmark.

Each case retains its query, scope, retrieved evidence, validated output and status. Keep real-data reports restricted. CLI reports include index manifest, case-file hash, split/seed, source-code hashes, dependency-lock hash, runtime and Git status. Captures made before committing code honestly show `git_commit: unavailable` and `git_dirty: true`; the source hashes identify the executed package. Use a clean committed checkout for a study.

## Authorized-data study

Use the same case JSONL contract as retrieval evaluation. Independently label queries and relevant sources, freeze settings on validation subjects, then run the same cases and `--split test --seed 42` for each comparator. The benchmark validates all relevance labels before generation. Empty selected splits and configuration errors fail the command; transport/model-output failures are case-level results. There is no automatic clinical scoring, bootstrap uncertainty, clinician adjudication or statistical comparison. Those require the prespecified [research protocol](research-protocol.md).
