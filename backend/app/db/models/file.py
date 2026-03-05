from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.user import User

class File(SQLModel, table=True):
    __tablename__ = "file"

    id: UUID = Field(default_factory=uuid4, sa_column=Column(PGUUID(as_uuid=True), nullable=False, primary_key=True, index=True))
    conversation_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False))
    message_id: Optional[UUID] = Field(default=None, sa_column=Column(PGUUID(as_uuid=True), ForeignKey("message.id"), nullable=True))
    user_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("user.id"), nullable=False))
    filename: str = Field(sa_column=Column(String, nullable=False))
    file_type: str = Field(sa_column=Column(String, nullable=False))
    file_size: int = Field(sa_column=Column(Integer, nullable=False))
    storage_path: str = Field(sa_column=Column(String, nullable=False))
    status: str = Field(default="uploaded", sa_column=Column(String, default="uploaded"))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False))

    # Relationships
    conversation: "Conversation" = Relationship(back_populates="files")
    message: Optional["Message"] = Relationship(back_populates="files")
    user: "User" = Relationship(back_populates="files")