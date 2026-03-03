from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional

class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    filename: str
    file_type: str
    size: int
    path: str
    processed: bool = False
    file_metadata: Optional[dict] = Field(
        sa_column=Column(JSONB) 
    )