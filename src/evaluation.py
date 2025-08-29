"""Evaluation utilities for the MIMIC‑IV demo summariser.

Since the patient summaries are generated algorithmically and there are
no ground‑truth human summaries, the usual summarisation metrics
such as ROUGE are less meaningful here.  Instead we provide two
simple evaluation functions:

* **retrieval accuracy:**  verify that querying the system with the
  patient’s identifier returns the correct summary.  This acts as a
  smoke test for the retrieval layer.
* **length statistics:**  compute basic statistics (min, max, mean) on
  the lengths of the generated summaries.
"""

from __future__ import annotations

from typing import Dict, List

from .summarizer import RetrievalSummariser


def evaluate_retrieval_accuracy(summaries: Dict[str, str]) -> float:
    """Compute the accuracy of retrieving the correct summary by patient id.

    Args:
        summaries: mapping of patient id to summary

    Returns:
        Fraction of patients for which querying the summariser by id returns
        their own summary as the top result.
    """
    ids: List[str] = list(summaries.keys())
    docs: List[str] = [summaries[pid] for pid in ids]
    retriever = RetrievalSummariser(docs)
    correct = 0
    for i, pid in enumerate(ids):
        # query with patient id (first eight characters to simulate partial ID search)
        query_str = pid[:8]
        results = retriever.query(query_str, top_k=1)
        if not results:
            continue
        top_summary = results[0][0]
        if top_summary == summaries[pid]:
            correct += 1
    return correct / len(ids) if ids else 0.0


def length_statistics(summaries: Dict[str, str]) -> Dict[str, float]:
    """Compute basic statistics on summary lengths.

    Args:
        summaries: mapping of patient id to summary text

    Returns:
        Dictionary with keys `min`, `max` and `mean` representing the
        minimum, maximum and average number of characters across the
        summaries.
    """
    lengths = [len(text) for text in summaries.values()]
    if not lengths:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": float(min(lengths)),
        "max": float(max(lengths)),
        "mean": float(sum(lengths) / len(lengths)),
    }
