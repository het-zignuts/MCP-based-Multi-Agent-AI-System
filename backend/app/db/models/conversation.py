from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Column

class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str = Field(sa_column=Column(String, nullable=False))
    conversation_metadata: Optional[dict] = Field(
        sa_column=Column(JSONB) 
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)