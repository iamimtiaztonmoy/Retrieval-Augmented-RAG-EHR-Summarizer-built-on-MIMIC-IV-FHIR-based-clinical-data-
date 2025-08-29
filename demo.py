#!/usr/bin/env python
"""Demo script to generate patient summaries and run simple retrieval queries.

This script loads the FHIR demo dataset, extracts basic patient
demographics and diagnostic conditions, builds summaries, evaluates
retrieval accuracy and prints a few example queries.  It also writes
the summaries to a CSV file under the `data/` directory.

Usage:
    python demo.py

Make sure that the `mimic_iv_project` package is on the Python path
(for example by running the script from the repository root) and that
the FHIR demo dataset has been extracted into the directory
`../mimic_iv_demo/mimic-iv-clinical-database-demo-on-fhir-2.1.0/fhir` relative to this file.  You can set a custom
environment variable `FHIR_DIR` to override the default path.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.data_utils_fhir import load_patients, load_conditions, build_patient_summaries, save_summaries_to_csv
from src.evaluation import evaluate_retrieval_accuracy, length_statistics
from src.summarizer import RetrievalSummariser


def main() -> None:
    # Determine the directory containing FHIR NDJSON files.  Allow
    # overriding via environment variable for flexibility.
    default_path = Path(__file__).resolve().parent.parent / "../mimic_iv_demo/mimic-iv-clinical-database-demo-on-fhir-2.1.0/fhir"
    fhir_dir = Path(os.environ.get("FHIR_DIR", default_path))
    if not fhir_dir.exists():
        raise FileNotFoundError(
            f"FHIR directory not found at {fhir_dir}. Set FHIR_DIR env var to the directory containing NDJSON files."
        )

    print(f"Loading FHIR resources from: {fhir_dir}")
    patients = load_patients(fhir_dir)
    print(f"Loaded {len(patients)} patients")
    conditions = load_conditions(fhir_dir)
    print(f"Loaded condition lists for {len(conditions)} patients")

    # Build summaries
    summaries = build_patient_summaries(patients, conditions)
    print(f"Generated summaries for {len(summaries)} patients")

    # Save to CSV
    out_csv = Path(__file__).resolve().parent / "data" / "patient_summaries.csv"
    save_summaries_to_csv(summaries, out_csv)
    print(f"Summaries saved to {out_csv}")

    # Evaluate retrieval accuracy (smoke test)
    acc = evaluate_retrieval_accuracy(summaries)
    print(f"Retrieval accuracy (using patient ID prefix) = {acc:.2%}")
    stats = length_statistics(summaries)
    print(
        f"Summary length statistics: min={stats['min']:.0f}, max={stats['max']:.0f}, mean={stats['mean']:.1f} characters"
    )

    # Demo queries
    retriever = RetrievalSummariser(list(summaries.values()))
    queries = [
        "heart failure",  # common condition query
        next(iter(patients.keys()))[:8],  # sample patient ID prefix
        "pneumonia diabetes"  # multi‑condition query
    ]
    print("\nExample queries:")
    for q in queries:
        results = retriever.query(q, top_k=1)
        best_summary = results[0][0] if results else "No result"
        print(f"\nQuery: {q}\nSummary: {best_summary}\n")


if __name__ == "__main__":
    main()
