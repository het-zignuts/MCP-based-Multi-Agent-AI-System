from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.enums import SourceKind, ValueSpecificity, OverwriteRisk, ProfileCategory, MemoryType, EvidenceType, TemporalScope              


class MemoryBase(BaseModel):
    content: str
    memory_type: str
    memory_metadata: dict = Field(default_factory=dict)
    importance_score: float = 0.5
    source: str = "conversation"
    conversation_id: Optional[UUID] = None


class MemoryCreate(MemoryBase):
    user_id: UUID
    embedding: Optional[list[float]] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    memory_metadata: Optional[dict] = None
    importance_score: Optional[float] = None
    source: Optional[str] = None
    is_active: Optional[bool] = None
    embedding: Optional[list[float]] = None


class MemoryRead(MemoryBase):
    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    embedding: Optional[list[float]] = None

    model_config = ConfigDict(from_attributes=True)

class MemoryComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relationship: Literal[
        "duplicate",
        "compatible",
        "conflict",
        "unrelated",
    ]
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    reason: str

class MemoryMetadata(BaseModel):
    source: str = "conversation"
    specificity_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    support_span_count: int = Field(
        default=0,
        ge=0,
    )
    is_generic_persona_claim: bool = False
    has_concrete_anchor: bool = False
    source_kind: SourceKind = SourceKind.unclear
    profile_write_eligible: bool = False
    profile_write_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    value_specificity: ValueSpecificity = ValueSpecificity.vague
    overwrite_risk: OverwriteRisk = OverwriteRisk.high
    profile_category: ProfileCategory = ProfileCategory.other
    profile_attributes: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

class ExtractedMemory(BaseModel):
    content: str
    memory_type: MemoryType
    importance_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    evidence: EvidenceType
    temporal_scope: TemporalScope
    memory_metadata: MemoryMetadata

class MemoryExtractionResponse(BaseModel):
    memories: list[ExtractedMemory] = []

from typing import Literal

from pydantic import BaseModel, Field


class MemoryProfileAnnotation(BaseModel):
    profile_category: Literal[
        "identity",
        "preference",
        "project",
        "relationship",
        "wellbeing",
        "other",
    ] = "other"

    profile_attributes: list[str] = []

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )