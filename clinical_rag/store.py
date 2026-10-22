"""Disk-backed evidence store. Scope is mandatory before ranking/limiting."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE chunks (
 id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, hadm_id TEXT NOT NULL,
 source TEXT NOT NULL, source_id TEXT NOT NULL, event_time TEXT NOT NULL,
 text TEXT NOT NULL
);
CREATE INDEX scope_idx ON chunks(subject_id, hadm_id);
CREATE VIRTUAL TABLE evidence USING fts5(text, content='chunks', content_rowid='rowid');
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path: Path, *, readonly: bool = True) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create(path: Path) -> sqlite3.Connection:
    # Never replace an existing data store implicitly.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass
    path.chmod(0o600)
    conn = connect(path, readonly=False)
    conn.executescript(SCHEMA)
    return conn


def add(conn, subject_id: str, hadm_id: str, source: str, source_id: str,
        event_time: str, text: str, *, chunk_size: int = 1200, overlap: int = 150):
    if not subject_id or not hadm_id or not text.strip():
        raise ValueError("Evidence requires subject, encounter, and text")
    if not 0 <= overlap < chunk_size:
        raise ValueError("Invalid chunk configuration")
    ids = []
    for start in range(0, len(text), chunk_size - overlap):
        piece = text[start:start + chunk_size]
        identity = [subject_id, hadm_id, source, source_id, event_time, start, piece]
        cid = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        conn.execute("INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?,?,?)",
                     (cid, subject_id, hadm_id, source, source_id, event_time, piece))
        ids.append(cid)
        if start + chunk_size >= len(text):
            break
    return ids


def finish(conn, manifest: dict):
    conn.execute("INSERT INTO evidence(evidence) VALUES ('rebuild')")
    conn.execute("INSERT INTO metadata VALUES ('manifest', ?)",
                 (json.dumps(manifest, sort_keys=True),))
    conn.commit()


def manifest(conn) -> dict:
    row = conn.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
    if row is None:
        raise ValueError("Incomplete index: rebuild from source")
    return json.loads(row[0])


def retrieve(conn, subject_id: str, hadm_id: str, query: str, top_k: int = 6) -> list[dict]:
    if not subject_id or not hadm_id:
        raise ValueError("Both subject_id and hadm_id are required")
    if not 1 <= top_k <= 20 or len(query) > 2000:
        raise ValueError("Invalid retrieval limits")
    # Do not allow caller-supplied FTS operators or arbitrary SQL.
    terms = list(dict.fromkeys(re.findall(r"[^\W_]+", query.lower(), re.UNICODE)))[:64]
    if not terms:
        return []
    expression = " OR ".join('"' + term + '"' for term in terms)
    rows = conn.execute("""
        SELECT c.*, bm25(evidence) AS rank FROM evidence
        JOIN chunks c ON c.rowid = evidence.rowid
        WHERE evidence MATCH ? AND c.subject_id = ? AND c.hadm_id = ?
        ORDER BY rank ASC, c.id ASC LIMIT ?
    """, (expression, subject_id, hadm_id, top_k)).fetchall()
    return [dict(row) for row in rows]
