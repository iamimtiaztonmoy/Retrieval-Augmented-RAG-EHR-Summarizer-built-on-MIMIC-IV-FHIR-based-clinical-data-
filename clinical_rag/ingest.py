"""Stream selected MIMIC-IV CSV tables into a retrospective encounter index.

No discharge-note input path exists. No credentials or download code is used.
Large event files stream row-by-row; encounter/dictionary maps remain in RAM.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
from pathlib import Path
import platform
import sqlite3

from . import __version__
from . import store


def table(root: Path, name: str) -> Path:
    for suffix in (".csv.gz", ".csv"):
        path = root / (name + suffix)
        if path.is_file():
            return path
    raise FileNotFoundError(f"Required table missing: {name}.csv[.gz]")


def rows(path: Path, required: set[str]):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required columns in {path.name}: {sorted(required)}")
        for row in reader:
            if None in row or any(row[k] is None for k in required):
                raise ValueError(f"Malformed CSV row in {path.name}")
            yield row


def timestamp(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo is None else None
    except (TypeError, ValueError):
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(hosp: Path, output: Path, *, note_dir: Path | None = None,
          subjects: set[str] | None = None, include_labs: bool = False,
          include_prescriptions: bool = False, dataset_version: str = "3.1",
          note_version: str = "2.2", synthetic: bool = False) -> dict:
    files = {name: table(hosp, name) for name in
             ("admissions", "diagnoses_icd", "d_icd_diagnoses")}
    if include_labs:
        files.update({name: table(hosp, name) for name in ("labevents", "d_labitems")})
    if include_prescriptions:
        files["prescriptions"] = table(hosp, "prescriptions")
    if note_dir is not None:
        files["radiology"] = table(note_dir, "radiology")
    counts = Counter()
    admissions = {}
    for r in rows(files["admissions"], {"subject_id", "hadm_id", "admittime", "dischtime"}):
        if subjects is not None and r["subject_id"] not in subjects:
            continue
        start, end = timestamp(r["admittime"]), timestamp(r["dischtime"])
        if not r["subject_id"] or not r["hadm_id"] or start is None or end is None or end < start:
            counts["invalid_admissions"] += 1
            continue
        key = (r["subject_id"], r["hadm_id"])
        if key in admissions:
            raise ValueError("Duplicate encounter in admissions")
        admissions[key] = (start, end)
    if not admissions:
        raise ValueError("No valid selected admissions")
    diagnoses = {(r["icd_code"], r["icd_version"]): r["long_title"]
                 for r in rows(files["d_icd_diagnoses"], {"icd_code", "icd_version", "long_title"})}
    conn = store.create(output)
    try:
        def emit(r, source, source_id, when, text):
            store.add(conn, r["subject_id"], r["hadm_id"], source, source_id, when, text)
            counts[source + "_included"] += 1

        def eligible(r, event_field, availability_field=None):
            interval = admissions.get((r["subject_id"], r["hadm_id"]))
            if interval is None:
                counts["unselected_or_unlinked"] += 1
                return False
            event = timestamp(r[event_field])
            available = timestamp(r.get(availability_field, "")) if availability_field else event
            if event is None or available is None:
                counts["missing_or_invalid_time"] += 1
                return False
            if not interval[0] <= event <= interval[1] or available > interval[1]:
                counts["outside_encounter_or_late"] += 1
                return False
            return True

        for i, r in enumerate(rows(files["diagnoses_icd"],
                                   {"subject_id", "hadm_id", "icd_code", "icd_version", "seq_num"})):
            if (r["subject_id"], r["hadm_id"]) not in admissions:
                counts["unselected_or_unlinked"] += 1
                continue
            label = diagnoses.get((r["icd_code"], r["icd_version"]), r["icd_code"])
            emit(r, "diagnoses_icd", str(i + 2), "",
                 f"Retrospective billing diagnosis (not onset): ICD-{r['icd_version']} "
                 f"{r['icd_code']}; {label}; sequence={r['seq_num']}.")

        if include_labs:
            labels = {r["itemid"]: r["label"] for r in
                      rows(files["d_labitems"], {"itemid", "label"})}
            required = {"subject_id", "hadm_id", "labevent_id", "itemid", "charttime", "storetime", "value", "valueuom"}
            for r in rows(files["labevents"], required):
                if eligible(r, "charttime", "storetime"):
                    emit(r, "labevents", r["labevent_id"], r["charttime"],
                         f"Lab recorded at {r['charttime']} (stored {r['storetime']}): "
                         f"{labels.get(r['itemid'], r['itemid'])} = {r['value']} {r['valueuom']}.")

        if include_prescriptions:
            required = {"subject_id", "hadm_id", "pharmacy_id", "starttime", "drug", "dose_val_rx", "dose_unit_rx", "route"}
            for i, r in enumerate(rows(files["prescriptions"], required)):
                if eligible(r, "starttime"):
                    emit(r, "prescriptions", f"{r['pharmacy_id']}:{i + 2}", r["starttime"],
                         f"Prescription order starting {r['starttime']}: {r['drug']} "
                         f"{r['dose_val_rx']} {r['dose_unit_rx']}, route={r['route']}. "
                         "Order does not establish administration or discharge medication.")

        if note_dir is not None:
            required = {"subject_id", "hadm_id", "note_id", "charttime", "storetime", "text"}
            for r in rows(files["radiology"], required):
                if eligible(r, "charttime", "storetime"):
                    emit(r, "radiology", r["note_id"], r["charttime"], r["text"])

        manifest = {
            "project_version": __version__, "dataset": "synthetic-fixture" if synthetic else "MIMIC-IV",
            "dataset_version": dataset_version, "note_version": note_version if note_dir else None,
            "task": "retrospective_encounter_evidence_summary", "admissions": len(admissions),
            "counts": dict(counts), "files": {k: {"sha256": sha256(p), "bytes": p.stat().st_size}
                                               for k, p in files.items()},
            "subject_filter": sorted(subjects) if subjects is not None else None,
            "chunk_size_chars": 1200, "overlap_chars": 150,
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "discharge_notes_indexed": False,
        }
        store.finish(conn, manifest)
        return manifest
    except BaseException:
        conn.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
