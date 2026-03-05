from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Column

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)