"""Authenticated local research API. Bind to loopback; not a multi-user deployment."""
from __future__ import annotations
import hmac
import os
from pathlib import Path
import sqlite3
from typing import Annotated
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .schemas import RetrievalResponse, SummaryResponse
from clinical_rag import store
from clinical_rag.generation import summarize

app = FastAPI(title="Encounter Evidence Summarizer", version="0.2.0")


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    subject_id: str = Field(min_length=1, max_length=64)
    hadm_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)


def authorized(authorization: Annotated[str | None, Header()] = None):
    token = os.getenv("RAG_API_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Configure RAG_API_TOKEN with at least 32 characters")
    if not authorization or not hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})


def database():
    path = os.getenv("RAG_DB")
    if not path:
        raise HTTPException(503, "Index not configured")
    conn = None
    try:
        conn = store.connect(Path(path))
        store.manifest(conn)
        yield conn
    except (sqlite3.Error, ValueError, OSError):
        raise HTTPException(503, "Index unavailable or invalid") from None
    finally:
        if conn is not None:
            conn.close()


@app.get("/health")
def health():
    return {"status": "ok", "clinical_validation": False}


@app.get("/ready", dependencies=[Depends(authorized)])
def ready(conn=Depends(database)):
    count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    conn.execute("SELECT rowid FROM evidence WHERE evidence MATCH 'readinessprobe' LIMIT 1").fetchall()
    if not count:
        raise HTTPException(503, "Index contains no evidence")
    return {"status": "ready", "chunks": count, "model_checked": False}


@app.post("/v1/retrieve", dependencies=[Depends(authorized)], response_model=RetrievalResponse)
def retrieval(request: RetrievalRequest, conn=Depends(database)):
    evidence = store.retrieve(conn, request.subject_id, request.hadm_id, request.query, request.top_k)
    return {"evidence": evidence, "abstained": not evidence}


@app.post("/v1/summarize", dependencies=[Depends(authorized)],
          response_model=SummaryResponse, response_model_exclude_unset=True)
def summary(request: RetrievalRequest, conn=Depends(database)):
    evidence = store.retrieve(conn, request.subject_id, request.hadm_id, request.query, request.top_k)
    try:
        result = summarize(evidence, request.query, backend=os.getenv("RAG_BACKEND", "extractive"),
                           model=os.getenv("RAG_MODEL"),
                           base_url=os.getenv("RAG_MODEL_URL", "http://127.0.0.1:11434"))
    except (OSError, TimeoutError):
        raise HTTPException(502, "Local model unavailable") from None
    except ValueError:
        raise HTTPException(503, "Invalid local model configuration") from None
    result["evidence"] = [r for r in evidence if r["id"] in result["evidence_ids"]]
    return result
