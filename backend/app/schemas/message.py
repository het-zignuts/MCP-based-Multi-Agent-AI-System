from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.schemas.file import FileRead

class MessageCreate(BaseModel):
    conversation_id: UUID
    user_id: UUID
    content: str
    token_count: Optional[int] = None
    file_ids: Optional[List[UUID]] = []

class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    content: str
    token_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    files: Optional[List["FileRead"]] = []  

    class Config:
        orm_mode = True

from app.schemas.file import FileRead
MessageRead.update_forward_refs()