"""Run with python -m clinical_rag --help. Outputs stay local."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from . import store
from .evaluation import evaluate, subject_split
from .generation import summarize
from .ingest import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--hosp", type=Path, required=True)
    ingest.add_argument("--notes", type=Path)
    ingest.add_argument("--db", type=Path, required=True)
    ingest.add_argument("--subjects", type=Path, help="Local text file: one subject_id per line")
    ingest.add_argument("--labs", action="store_true")
    ingest.add_argument("--prescriptions", action="store_true")
    ingest.add_argument("--dataset-version", default="3.1")
    ingest.add_argument("--note-version", default="2.2")
    ingest.add_argument("--synthetic", action="store_true", help="Label authored fixtures; never use for real data")
    for name in ("retrieve", "summarize"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--db", type=Path, required=True)
        cmd.add_argument("--subject-id", required=True)
        cmd.add_argument("--hadm-id", required=True)
        cmd.add_argument("--query", required=True)
        cmd.add_argument("--top-k", type=int, default=6)
        cmd.add_argument("--out", type=Path, required=True)
        if name == "summarize":
            cmd.add_argument("--backend", choices=["extractive", "ollama"], default="extractive")
            cmd.add_argument("--model")
            cmd.add_argument("--model-url", default="http://127.0.0.1:11434")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--db", type=Path, required=True)
    ev.add_argument("--cases", type=Path, required=True)
    ev.add_argument("--top-k", type=int, default=6)
    ev.add_argument("--split", choices=["all", "train", "validation", "test"], default="test")
    ev.add_argument("--seed", default="42")
    ev.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "ingest":
        subjects = set(args.subjects.read_text().split()) if args.subjects else None
        result = build(args.hosp, args.db, note_dir=args.notes, subjects=subjects,
                       include_labs=args.labs, include_prescriptions=args.prescriptions,
                       dataset_version=args.dataset_version, note_version=args.note_version,
                       synthetic=args.synthetic)
        print(json.dumps({"admissions": result["admissions"], "counts": result["counts"]}, indent=2))
        return
    with store.connect(args.db) as conn:
        metadata = store.manifest(conn)
        if args.command == "evaluate":
            content = args.cases.read_bytes()
            cases = [json.loads(line) for line in content.decode().splitlines() if line.strip()]
            if args.split != "all":
                cases = [c for c in cases if subject_split(c["subject_id"], args.seed) == args.split]
            result = evaluate(conn, cases, args.top_k)
            result.update({"cases_sha256": hashlib.sha256(content).hexdigest(),
                           "split": args.split, "split_seed": args.seed})
        else:
            evidence = store.retrieve(conn, args.subject_id, args.hadm_id, args.query, args.top_k)
            if args.command == "retrieve":
                result = {"evidence": evidence, "abstained": not evidence}
            else:
                result = summarize(evidence, args.query, backend=args.backend, model=args.model,
                                   base_url=args.model_url)
                result["evidence"] = [e for e in evidence if e["id"] in result["evidence_ids"]]
            result.update({"subject_id": args.subject_id, "hadm_id": args.hadm_id,
                           "query": args.query, "top_k": args.top_k})
        result["index_manifest"] = metadata
    try:
        result["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        result["git_commit"] = "unavailable"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    args.out.chmod(0o600)
    print(f"Saved {args.command} output locally")


if __name__ == "__main__":
    main()
