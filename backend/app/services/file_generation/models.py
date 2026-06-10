from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GenerationFormat = Literal["txt", "md", "json", "csv", "pdf"]


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


@dataclass
class ArtifactRenderedFile:
    filename: str
    storage_path: str
    mime_type: str
    extension: str
    file_size: int
    preview_text: str


@dataclass
class GenerationDecision:
    should_generate: bool
    format: GenerationFormat | None
    confidence: float
    reason: str
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
