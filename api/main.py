"""FastAPI application exposing a simple summary service.

The API provides two endpoints:

* **GET /health** — liveness check.
* **GET /summary** — given a `patient_id` or a free‑text `query`,
  return the most relevant patient summary.  If an exact patient id is
  provided and found, that summary is returned.  Otherwise the query
  string is used in a retrieval over all summaries.

Start the server locally with:

```bash
uvicorn api.main:app --reload --port 8000
```

This file lives under the `api/` package so that it can be run
independently of the rest of the project.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from src.summarizer import RetrievalSummariser

app = FastAPI(title="MIMIC‑IV Demo Summarisation API")


@lru_cache(maxsize=1)
def _load_summaries() -> Dict[str, str]:
    """Load patient summaries from the CSV file.

    Returns:
        Mapping of patient id to summary text.
    """
    csv_path = Path(__file__).resolve().parent.parent / "data" / "patient_summaries.csv"
    summaries: Dict[str, str] = {}
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Expected summary CSV at {csv_path}, please run demo.py to generate it."
        )
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summaries[row["patient_id"]] = row["summary"]
    return summaries


@lru_cache(maxsize=1)
def _init_retriever() -> RetrievalSummariser:
    """Instantiate the retrieval summariser from loaded summaries."""
    summaries = _load_summaries()
    docs: List[str] = list(summaries.values())
    return RetrievalSummariser(docs)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/summary")
def get_summary(
    patient_id: Optional[str] = Query(None, description="Exact patient UUID"),
    query: Optional[str] = Query(None, description="Free text query")
):
    """Return a summary for a patient ID or a query string.

    If `patient_id` is provided and found in the summaries, the
    corresponding summary is returned directly.  Otherwise, the
    retrieval engine is used with the provided `query` (or the
    patient_id string) to find the most similar summary.
    """
    summaries = _load_summaries()
    retriever = _init_retriever()
    if patient_id and patient_id in summaries:
        return {"patient_id": patient_id, "summary": summaries[patient_id]}
    # Determine which query string to use
    q = query or patient_id
    if not q:
        raise HTTPException(status_code=400, detail="Either patient_id or query must be provided")
    results = retriever.query(q, top_k=3)
    if not results:
        raise HTTPException(status_code=404, detail="No summaries found for the given query")
    response = []
    # Map back to patient ids by matching summary text; this is O(n)
    inv_map = {v: k for k, v in summaries.items()}
    for summary_text, score in results:
        pid = inv_map.get(summary_text, "unknown")
        response.append({"patient_id": pid, "summary": summary_text, "score": score})
    return {"results": response}
