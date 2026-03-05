from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Column

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    role: str = Field(sa_column=Column(String, nullable=False))
    content: str = Field(sa_column=Column(String, nullable=False))
    token_count: Optional[int] = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)