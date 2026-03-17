from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.schemas.user import UserRead
from app.schemas.file import FileRead

class ConversationCreate(BaseModel):
    title: str
    user_id: UUID
    convo_metadata: Optional[dict] = None

class ConversationRead(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    convo_metadata: Optional[dict] = None
    user_id: UUID
    files: List[FileRead] = []

    class Config:
        orm_mode = True

ConversationRead.update_forward_refs()