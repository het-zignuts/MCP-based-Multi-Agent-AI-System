from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class FileCreate(BaseModel):
    conversation_id: UUID
    user_id: UUID
    message_id: Optional[UUID] = None
    filename: str
    file_type: str
    file_size: int
    storage_path: str

class FileRead(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: Optional[UUID] = None
    user_id: UUID
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
