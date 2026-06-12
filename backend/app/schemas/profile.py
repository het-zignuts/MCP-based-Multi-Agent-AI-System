from typing import Literal

from pydantic import BaseModel, Field


class ProfileCandidateMetadata(BaseModel):
    support_span_count: int = Field(default=0, ge=0)
    has_concrete_anchor: bool = False

class ProfileCandidate(BaseModel):
    category: str = "other"

    label: str
    value: str
    summary: str

    section: Literal[
        "preferences",
        "facts",
        "active_goals",
        "decisions",
    ] = "facts"

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    should_write_profile: bool = False

    write_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    source_kind: Literal[
        "statement",
        "question",
        "request",
        "correction",
        "assistant_claim",
        "hypothetical",
        "unclear",
    ] = "unclear"

    value_specificity: Literal[
        "concrete",
        "vague",
    ] = "vague"

    overwrite_risk: Literal[
        "none",
        "low",
        "high",
    ] = "high"

    evidence_type: Literal[
        "explicit",
        "repeated",
        "inferred",
    ] = "inferred"

    temporal_scope: Literal[
        "durable",
        "ongoing",
    ]

    evidence_text: str = ""

    tags: list[str] = []

    redundancy_key: str = ""

    metadata: ProfileCandidateMetadata = Field(
        default_factory=ProfileCandidateMetadata
    )

class ProfileCandidateResponse(BaseModel):
    candidates: list[ProfileCandidate] = Field(
        default_factory=list
    )