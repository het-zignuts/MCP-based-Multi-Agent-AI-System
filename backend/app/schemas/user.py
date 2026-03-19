from __future__ import annotations
from pydantic import BaseModel, EmailStr
from typing import List
from uuid import UUID
from datetime import datetime

from app.schemas.conversation import ConversationBasicRead

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime
    is_active: bool
    conversations: List["ConversationBasicRead"] = []

    class Config:
        orm_mode = True