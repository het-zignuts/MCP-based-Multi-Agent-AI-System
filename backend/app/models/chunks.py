from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy import Column, JSON
from pgvector.sqlalchemy import Vector

class Chunk(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    file_id: UUID
    content: str
    file_metadata: dict = Field(
        default={},
        sa_column=Column("metadata",JSON)
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        sa_column=Column(Vector(384))  
    )