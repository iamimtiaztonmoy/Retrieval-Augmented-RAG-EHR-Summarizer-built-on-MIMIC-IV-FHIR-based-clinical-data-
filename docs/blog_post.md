# Building a Retrieval‑Augmented Patient Summariser with MIMIC‑IV Demo Data

*29 August 2025*

The rise of large language models and retrieval‑augmented generation has sparked enormous interest in building AI systems that can understand and summarise clinical information.  Yet real‑world electronic health record (EHR) data are often difficult to access and messy to work with.  Fortunately, the MIT Laboratory for Computational Physiology provides an **open‑access MIMIC‑IV Clinical Database Demo** that converts a small subset of the MIMIC‑IV database into the FHIR (Fast Healthcare Interoperability Resources) format.  This post walks through how I built a simple retrieval‑based summarisation system on top of that dataset.

## What’s in the demo dataset?

The demo is a 100‑patient slice of the full MIMIC‑IV v2.2 and MIMIC‑IV‑ED v2.2 databases.  It contains FHIR resources in NDJSON format, such as `Patient`, `Condition`, `Medication`, `Observation` and many more.  Each resource is a JSON object on its own line, compressed with gzip.  Because the data are de‑identified and synthetic, there is no risk of exposing protected health information.  However, the dates have been shifted far into the future (e.g., birth dates in the 2080s) to further protect privacy.

For this project I focused on two resource types:

* **Patient** — provides basic demographics (gender and birthDate).
* **Condition** — lists diagnoses assigned to the patient, with ICD‑9/10 codes and human‑readable descriptions.

Other resources such as medications, procedures or observations could be added later to enrich the summaries.

## Parsing NDJSON into patient summaries

The first task was to parse the FHIR files.  I wrote a few helper functions in [`data_utils_fhir.py`](../src/data_utils_fhir.py) to:

* Read a compressed NDJSON file line by line and parse each JSON object.
* Build a map of patient IDs to their gender and birth date from the `Patient` resources.
* Build a map of patient IDs to a list of condition descriptions from the `Condition` resources (falling back on ICD codes if descriptions are missing).
* Generate a human‑readable summary string for each patient, e.g.:

  > Patient `0a8eebfd-a352-...`: gender=female, birthDate=2083-04-10. Diagnosed conditions include: Other dependence on machines, supplemental oxygen, Septicemia, Hypertension, ...

These summaries are stored in a CSV file (`data/patient_summaries.csv`) and also kept in memory for downstream tasks.

## Adding a retrieval layer

To make the summaries searchable, I added a simple retrieval layer using scikit‑learn’s `TfidfVectorizer`.  This converts the corpus of summaries into TF‑IDF vectors and computes cosine similarity between a user’s query and each summary.  The `RetrievalSummariser` class in [`summarizer.py`](../src/summarizer.py) encapsulates this logic.  It supports queries by patient identifier or free‑text, returning the most relevant summaries along with similarity scores.

For example:

```python
summaries = {...}  # mapping of patient id to summary text
retriever = RetrievalSummariser(list(summaries.values()))
results = retriever.query("heart failure", top_k=3)
```

Even with this simple approach, the retrieval accuracy was 100 % when searching by patient ID prefixes, and condition keywords like “septicemia” or “hypertension” returned reasonable matches.

## A lightweight API

To expose the functionality, I wrapped everything in a tiny FastAPI application (`api/main.py`).  The `/summary` endpoint accepts either a `patient_id` or a free‑text `query`.  If a valid patient ID is provided, it returns that patient’s summary.  Otherwise it uses the retrieval layer to find the top matching summaries.  Running the server locally is as simple as:

```bash
uvicorn api.main:app --reload --port 8000
```

You can then query it with curl:

```bash
curl "http://localhost:8000/summary?patient_id=0a8eebfd-a352-522e-89f0-1d4a13abdebc"

curl "http://localhost:8000/summary?query=hypertension%20diabetes"
```

## Limitations and next steps

This project barely scratches the surface of what’s possible with FHIR data.  The summaries are purely deterministic and list conditions verbatim.  There is no notion of problem onset or resolution, severity, or temporal progression.  Nor are medications, procedures or lab results included.  In a production setting one would also need to handle data quality issues (duplicate codes, missing descriptions) and implement robust error handling.

Future directions include:

* Parsing additional resource types (e.g., `MedicationRequest`, `Observation`) and adding them to the summary.
* Using language models to generate more natural‑sounding summaries while grounding them in the retrieved data.
* Implementing a full RAG pipeline with a knowledge base (vector store) and a generative model to answer arbitrary clinical questions about the patients.

Nevertheless, this exercise demonstrates how even a small open dataset can be used to explore core techniques like FHIR parsing, TF‑IDF retrieval and API design.  If you’d like to experiment yourself, clone the repo, run `demo.py`, and start hacking!
