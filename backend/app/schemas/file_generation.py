from __future__ import annotations

from typing import Optional, Literal
from uuid import UUID
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, Field

# from app.services.file_generation.models import GenerationFormat


GenerationFormat = Literal["txt", "md", "json", "csv", "pdf"]

class FileGenerationRequest(BaseModel):
    conversation_id: UUID
    user_id: UUID
    prompt: str
    output_format: GenerationFormat | None = None
    file_ids: list[UUID] = Field(default_factory=list)
    explicit_action: str | None = None


class FileGenerationPreviewResponse(BaseModel):
    decision: dict
    document: dict
    preview: dict


class GeneratedFileRead(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class FileGenerationResultResponse(BaseModel):
    decision: dict
    preview: dict
    download_url: str
    file: GeneratedFileRead
    assistant_message_id: Optional[UUID] = None


class ArtifactTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ArtifactSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    table: ArtifactTable | None = None


class ArtifactDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    summary: str = ""
    sections: list[ArtifactSection] = Field(default_factory=list)
    records: list[dict[str, str]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

class FileGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = ""
    document: ArtifactDocument


@dataclass
class ArtifactRenderedFile:
    filename: str
    storage_path: str
    mime_type: str
    extension: str
    file_size: int
    preview_text: str


class GenerationDecision(BaseModel):
    should_generate: bool
    format: GenerationFormat | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    source: str = "heuristic"


@dataclass
class GenerationOutcome:
    decision: GenerationDecision
    document: ArtifactDocument | None
    rendered_file: ArtifactRenderedFile | None
    file_record: object | None
    warnings: list[str]
    stm_state: dict
    download_url: str | None
    user_message: object | None = None
    assistant_message: object | None = None

