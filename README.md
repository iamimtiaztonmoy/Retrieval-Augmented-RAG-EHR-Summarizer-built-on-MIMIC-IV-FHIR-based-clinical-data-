# MIMIC‑IV Clinical Demo Summarization Project

This repository contains an end‑to‑end demonstration of parsing the **MIMIC‑IV Clinical Database Demo on FHIR** (version 2.1.0) and producing concise summaries for each patient.  The goal of the project is to showcase how to work with real FHIR resources to build a simple retrieval‑augmented summarization service.

The demo dataset, published by the MIT Laboratory for Computational Physiology, includes a 100‑patient subset of the MIMIC‑IV v2.2 and MIMIC‑IV‑ED v2.2 clinical databases converted into Fast Healthcare Interoperability Resources (FHIR) format.  Unlike the full MIMIC‑IV database, this demo is **open access** and does not require credentialed access.  All files are NDJSON files compressed as `.gz`.

## Project structure

```
mimic_iv_project/
├── data/
│   ├── patient_summaries.csv        # tabular file with one row per patient and a generated summary
│   ├── patients.json                # JSON mapping patient id to demographics and conditions
│   └── ...
├── src/
│   ├── data_utils_fhir.py           # functions for loading and parsing FHIR NDJSON files
│   ├── summarizer.py                # retrieval‑augmented summarization class
│   └── evaluation.py                # simple utility functions for evaluation (optional)
├── api/
│   └── main.py                      # FastAPI application exposing a /summary endpoint
├── demo.py                          # script demonstrating parsing and summarisation on a few patients
├── docs/
│   └── blog_post.md                 # narrative description of the project and its motivation
└── README.md                        # this file
```

## Running the demo

1.  Extract the demo dataset into a directory on your machine.  The scripts assume the following relative layout:

    ```
    mimic-iv-clinical-database-demo-on-fhir-2.1.0/
    └── fhir/
        ├── MimicPatient.ndjson.gz
        ├── MimicCondition.ndjson.gz
        └── ...
    ```

2.  Install the required Python packages (all are standard library except `fastapi` and `uvicorn` for the API):

    ```bash
    pip install fastapi uvicorn scikit-learn
    ```

3.  Parse the FHIR NDJSON files and generate patient summaries:

    ```bash
    python demo.py
    ```

    The script will load the patient and condition resources, build a summary string for each patient and evaluate the retrieval‑augmented summariser on a few example queries.  It will also save the CSV file `data/patient_summaries.csv`.

4.  To run the API server locally:

    ```bash
    uvicorn api.main:app --reload --port 8000
    ```

    Once running, you can request a summary for a patient ID:

    ```
    curl "http://localhost:8000/summary?patient_id=0a8eebfd-a352-522e-89f0-1d4a13abdebc"
    ```

## Notes

*  **Scope:**  This project is intended as an educational demonstration.  The generated summaries are simplistic: they list the patient’s gender, age (derived from birth date relative to the synthetic FHIR date system), and all diagnostic conditions extracted from the `MimicCondition` file.  There is no clinical interpretation or medication extraction.
*  **Privacy:**  The demo dataset is fully de‑identified and synthetic.  Do not attempt to use this code with the full credentialed MIMIC‑IV database unless you have the appropriate Data Use Agreement (DUA) and approvals.
*  **Extensibility:**  The `data_utils_fhir.py` module is written to be easily extended.  For example, you can add functions to parse `MedicationRequest`, `Observation` or other FHIR resources and augment the summaries.
