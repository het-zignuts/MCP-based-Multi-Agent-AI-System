from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Text, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

class UserProfileSnapshot(SQLModel, table=True):
    __tablename__ = "user_profile_snapshot"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )

    user_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )

    profile_text: str = Field(
        default="",
        sa_column=Column(Text, nullable=False, default=""),
    )

    profile_items: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )

    preferences: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )

    facts: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )

    active_goals: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )

    decisions: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )

    source_memory_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False),
    )
