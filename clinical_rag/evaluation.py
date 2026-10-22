"""Label-based source retrieval metrics, not clinical summary quality."""
from __future__ import annotations
import hashlib
from statistics import mean
from .store import retrieve


def subject_split(subject_id: str, seed: str = "42") -> str:
    bucket = int(hashlib.sha256(f"{seed}:{subject_id}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def evaluate(conn, cases: list[dict], top_k: int = 6) -> dict:
    if not cases:
        raise ValueError("No labeled cases to evaluate")
    recalls, reciprocal_ranks, hits, negatives = [], [], [], []
    records, seen = [], set()
    for case in cases:
        required = {"case_id", "subject_id", "hadm_id", "query", "relevant_sources"}
        if not required.issubset(case) or case["case_id"] in seen:
            raise ValueError("Missing case fields or duplicate case_id")
        seen.add(case["case_id"])
        gold = case["relevant_sources"]
        if not isinstance(gold, list) or any(not isinstance(x, str) or ":" not in x for x in gold):
            raise ValueError("relevant_sources must be source:source_id strings")
        gold = set(gold)
        available = {r[0] + ":" + r[1] for r in conn.execute(
            "SELECT source, source_id FROM chunks WHERE subject_id=? AND hadm_id=?",
            (case["subject_id"], case["hadm_id"]))}
        if not gold.issubset(available):
            raise ValueError("Gold source absent from encounter corpus")
        found = retrieve(conn, case["subject_id"], case["hadm_id"], case["query"], top_k)
        # k counts chunks; repeated chunks of a source count once for source metrics.
        ids = list(dict.fromkeys(r["source"] + ":" + r["source_id"] for r in found))
        rank = next((i + 1 for i, sid in enumerate(ids) if sid in gold), None)
        if gold:
            recalls.append(len(gold.intersection(ids)) / len(gold))
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            hits.append(float(rank is not None))
        else:
            negatives.append(float(not found))
        records.append({"case_id": case["case_id"], "retrieved_sources": ids,
                        "relevant_sources": sorted(gold), "abstained_retrieval": not found})
    return {"cases": len(cases), "positive_cases": len(recalls), "negative_cases": len(negatives),
            "top_k_chunks": top_k, "source_recall_at_k": mean(recalls) if recalls else None,
            "source_mrr_at_k": mean(reciprocal_ranks) if recalls else None,
            "source_hit_rate_at_k": mean(hits) if hits else None,
            "negative_retrieval_abstention_rate": mean(negatives) if negatives else None,
            "records": records, "clinical_quality_evaluated": False}
