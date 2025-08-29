"""Utility functions for loading and parsing MIMIC‑IV FHIR demo data.

The demo dataset released by PhysioNet stores FHIR resources in NDJSON
format compressed with gzip.  Each file contains one resource per line
(a newline‑delimited JSON object).  This module provides helper
functions to read the relevant resources for this project and assemble
patient‑level summaries.

Only a tiny subset of the FHIR resources are used here:

* **Patient** – for demographics (gender, birthDate)
* **Condition** – for diagnostic conditions (ICD‑9/10 codes and descriptions)

You can extend the module to parse other resources (e.g. medications,
procedures, observations) by adding new functions.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Dict, List


def _open_ndjson_gz(path: Path):
    """Yield parsed JSON objects from a gzip‑compressed NDJSON file.

    Args:
        path: Path to a `.ndjson.gz` file.

    Yields:
        Dict representing each resource on each line.
    """
    with gzip.open(path, mode="rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines gracefully.
                continue


def load_patients(fhir_dir: Path) -> Dict[str, Dict[str, str]]:
    """Load patients and basic demographics from MimicPatient.ndjson.gz.

    Args:
        fhir_dir: directory containing FHIR NDJSON files (expects
                  MimicPatient.ndjson.gz inside).

    Returns:
        Mapping from patient UUID to a dict with keys `gender` and
        `birthDate` (may be missing if not provided).
    """
    patient_file = fhir_dir / "MimicPatient.ndjson.gz"
    patients: Dict[str, Dict[str, str]] = {}
    for resource in _open_ndjson_gz(patient_file):
        pid = resource.get("id")
        if not pid:
            continue
        patients[pid] = {
            "gender": resource.get("gender", "unknown"),
            "birthDate": resource.get("birthDate", "unknown"),
        }
    return patients


def load_conditions(fhir_dir: Path) -> Dict[str, List[str]]:
    """Load conditions grouped by patient from MimicCondition.ndjson.gz.

    Args:
        fhir_dir: directory containing FHIR NDJSON files (expects
                  MimicCondition.ndjson.gz inside).

    Returns:
        Mapping from patient UUID to a list of condition descriptions.
    """
    condition_file = fhir_dir / "MimicCondition.ndjson.gz"
    conditions_by_patient: Dict[str, List[str]] = {}
    for resource in _open_ndjson_gz(condition_file):
        # Find the patient this condition applies to
        subject_ref = resource.get("subject", {}).get("reference")
        if not subject_ref or not subject_ref.startswith("Patient/"):
            continue
        patient_id = subject_ref.split("/", 1)[1]

        # Extract descriptive label for the condition
        cond_desc = None
        code = resource.get("code", {})
        # Try `code.coding.display`
        for coding in code.get("coding", []):
            display = coding.get("display")
            if display:
                cond_desc = display
                break
        # Fallback to `code.text` or `coding.code`
        if not cond_desc:
            cond_desc = code.get("text") or None
        if not cond_desc:
            coding_list = code.get("coding", [])
            if coding_list:
                cond_desc = coding_list[0].get("code")
        if not cond_desc:
            cond_desc = "Unknown condition"

        conditions_by_patient.setdefault(patient_id, []).append(cond_desc)
    return conditions_by_patient


def build_patient_summaries(patients: Dict[str, Dict[str, str]],
                            conditions: Dict[str, List[str]]) -> Dict[str, str]:
    """Construct a summary string for each patient.

    The summary includes the patient’s gender, birth date and a list of
    unique condition descriptions.

    Args:
        patients: mapping of patient id to demographics
        conditions: mapping of patient id to list of conditions

    Returns:
        Mapping from patient id to a human‑readable summary string.
    """
    summaries: Dict[str, str] = {}
    for pid, demo in patients.items():
        gender = demo.get("gender", "unknown")
        birth = demo.get("birthDate", "unknown")
        conds = sorted(set(conditions.get(pid, [])))
        cond_str = ", ".join(conds) if conds else "None recorded"
        summaries[pid] = (
            f"Patient {pid}: gender={gender}, birthDate={birth}. "
            f"Diagnosed conditions include: {cond_str}."
        )
    return summaries


def save_summaries_to_csv(summaries: Dict[str, str], out_path: Path) -> None:
    """Save the patient summaries into a CSV file.

    Args:
        summaries: mapping from patient id to summary string
        out_path: path to the CSV file to write
    """
    import csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["patient_id", "summary"])
        for pid, summary in summaries.items():
            writer.writerow([pid, summary])
