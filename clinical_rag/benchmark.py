"""Batch generation audit; mechanical checks are not clinical quality scores."""
from __future__ import annotations

from collections import Counter
from statistics import mean
from time import perf_counter

from .evaluation import evaluate
from .generation import summarize
from .store import retrieve


def benchmark(conn, cases: list[dict], top_k: int = 6, *, backend="extractive",
              model=None, base_url="http://127.0.0.1:11434") -> dict:
    # Validate every relevance label before paying the cost of generation.
    retrieval = evaluate(conn, cases, top_k)
    if backend not in {"extractive", "ollama"}:
        raise ValueError("Unknown backend")
    if backend == "ollama" and not model:
        raise ValueError("An explicit local model is required")
    records = []
    failures = {"invalid_model_response", "citation_or_schema_validation_failed"}
    for case in cases:
        start = perf_counter()
        evidence = retrieve(conn, case["subject_id"], case["hadm_id"], case["query"], top_k)
        try:
            output = summarize(evidence, case["query"], backend=backend,
                               model=model, base_url=base_url)
            status = "validation_failure" if output["reason"] in failures else (
                "abstained" if output["abstained"] else "answered")
        except (OSError, TimeoutError):
            # Keep failed cases in the denominator. Never publish raw exception text.
            output = None
            status = "transport_failure"
        elapsed = perf_counter() - start
        records.append({"case_id": case["case_id"], "subject_id": case["subject_id"],
                        "hadm_id": case["hadm_id"], "query": case["query"],
                        "status": status, "elapsed_seconds": elapsed,
                        "output": output, "evidence": evidence})
    counts = Counter(r["status"] for r in records)
    return {"backend": backend, "requested_model": model, "cases": len(records),
            "status_counts": {s: counts[s] for s in
                ("answered", "abstained", "validation_failure", "transport_failure")},
            "answered_fraction": counts["answered"] / len(records),
            "mean_elapsed_seconds": mean(r["elapsed_seconds"] for r in records),
            "retrieval": retrieval, "records": records,
            "clinical_quality_evaluated": False,
            "interpretation": "Answer and validation rates are mechanical checks, not factuality or clinical accuracy."}
