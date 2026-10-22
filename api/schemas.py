"""Public response schemas; citation validation remains in the generation layer."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Response):
    id: str
    subject_id: str
    hadm_id: str
    source: str
    source_id: str
    event_time: str
    text: str
    rank: float


class Citation(Response):
    chunk_id: str
    quote: str


class Claim(Response):
    text: str
    citations: list[Citation]


class RetrievalResponse(Response):
    evidence: list[Evidence]
    abstained: bool


class ModelMetadata(Response):
    model: str
    model_digest: str | None = None
    temperature: float | None = None
    seed: int | None = None
    num_ctx: int | None = None
    num_predict: int | None = None
    usage: dict[str, int] | None = Field(default=None,
        description="Ollama token counts and duration fields; durations are nanoseconds.")


class SummaryResponse(Response):
    abstained: bool
    claims: list[Claim]
    reason: Literal["no_matching_evidence", "invalid_model_response",
                    "citation_or_schema_validation_failed", "insufficient_evidence"] | None
    backend: Literal["extractive", "ollama"]
    prompt_version: str
    prompt_sha256: str
    evidence_ids: list[str]
    model: ModelMetadata | None
    evidence: list[Evidence]
