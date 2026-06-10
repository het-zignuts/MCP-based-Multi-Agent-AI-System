from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.file_generation.models import GenerationFormat


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

