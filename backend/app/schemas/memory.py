from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
