"""Retrieval‑based summariser for patient summaries.

This module implements a lightweight information‑retrieval (IR) layer
over the patient summaries produced from the MIMIC‑IV demo dataset.
Given a query string (for example, a patient identifier or a set of
keywords), the summariser retrieves the most similar summary using
TF‑IDF features and cosine similarity.  It can then return the
summary verbatim or apply optional post‑processing.

Usage:

```python
from src.summariser import RetrievalSummariser
summariser = RetrievalSummariser(list_of_summaries)
result = summariser.query("0a8eebfd")  # returns best matching summary
```
"""

from __future__ import annotations

from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


class RetrievalSummariser:
    """A simple retrieval‑augmented summariser using TF‑IDF.

    Args:
        documents: list of documents (patient summaries).  Each document
            is treated as a single text to retrieve against.
    """

    def __init__(self, documents: List[str]) -> None:
        self.documents = documents
        self.vectoriser = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectoriser.fit_transform(documents)

    def _similarities(self, query: str) -> List[Tuple[int, float]]:
        """Compute similarity scores between a query and all documents.

        Args:
            query: free‑text query

        Returns:
            List of tuples (index, score) sorted by decreasing score.
        """
        if not query:
            return []
        q_vec = self.vectoriser.transform([query])
        cosine_similarities = linear_kernel(q_vec, self.matrix).flatten()
        indexed = list(enumerate(cosine_similarities))
        ranked = sorted(indexed, key=lambda x: x[1], reverse=True)
        return ranked

    def query(self, query: str, top_k: int = 1) -> List[Tuple[str, float]]:
        """Retrieve the top‑k summaries most relevant to the query.

        Args:
            query: free‑text query or patient id
            top_k: number of documents to return

        Returns:
            List of tuples (summary, score) in descending order of score.
        """
        ranked = self._similarities(query)
        results: List[Tuple[str, float]] = []
        for idx, score in ranked[:top_k]:
            results.append((self.documents[idx], float(score)))
        return results
