from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.schemas.file import FileRead
    from app.schemas.message import MessageRead

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
    messages: List["MessageRead"] = []
    files: List["FileRead"] = []

    class Config:
        orm_mode = True

class ConversationBasicRead(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    convo_metadata: Optional[dict] = None
    user_id: UUID

    class Config:
        orm_mode = True


from app.schemas.file import FileRead
from app.schemas.message import MessageRead
ConversationRead.update_forward_refs()