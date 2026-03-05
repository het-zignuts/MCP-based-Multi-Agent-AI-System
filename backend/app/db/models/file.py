from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from sqlalchemy import String, Column

class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    filename: str = Field(sa_column=Column(String, nullable=False))
    file_type: str = Field(sa_column=Column(String, nullable=False))
    size: int
    path: str = Field(sa_column=Column(String, nullable=False))
    processed: bool = False
    file_metadata: Optional[dict] = Field(
        sa_column=Column(JSONB) 
    )