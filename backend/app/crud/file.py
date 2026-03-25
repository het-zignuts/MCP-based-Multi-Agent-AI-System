from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
import anyio
from fastapi import HTTPException, UploadFile
from uuid import UUID
from datetime import datetime
import os
import uuid

from app.db.models.file import File
from app.db.models.user import User
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.schemas.file import FileRead
from app.services.file_type_config import ALLOWED_FILE_EXTENSIONS


def _write_file_content(file_path: str, content: bytes) -> None:
    with open(file_path, "wb") as f:
        f.write(content)

async def create_file(db: AsyncSession, payload) -> File:
    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    conversation = (await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))).scalar_one_or_none()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    if payload.message_id:
        message = (await db.execute(select(Message).where(Message.id == payload.message_id))).scalar_one_or_none()
        if not message:
            raise HTTPException(404, "Message not found")

    file = File(
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        message_id=payload.message_id,  # can be None
        filename=payload.filename,
        file_type=payload.file_type,
        file_size=payload.file_size,
        storage_path=payload.storage_path,
        status="uploaded"
    )
    db.add(file)
    await db.commit()

    result = await db.execute(
        select(File)
        .where(File.id == file.id)
        .options(
            selectinload(File.user),
            selectinload(File.conversation),
            selectinload(File.message),
        )
    )

    file = result.scalar_one()
    return file

async def get_file(db: AsyncSession, file_id: UUID) -> File:
    result = await db.execute(select(File).where(File.id == file_id).options(selectinload(File.user), selectinload(File.conversation), selectinload(File.message)))
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")
    return file

async def get_files(db: AsyncSession, conversation_id: UUID, message_id: UUID | None = None) -> list[File]:
    query = select(File).options(selectinload(File.user), selectinload(File.conversation), selectinload(File.message))
    if conversation_id:
        query = query.where(File.conversation_id == conversation_id)
    if message_id:
        query = query.where(File.message_id == message_id)
    result = await db.execute(query)
    return result.scalars().all()

async def update_file(db: AsyncSession, file_id: UUID, message_id: UUID | None = None, status: str | None = None) -> File:
    file = await get_file(db, file_id)
    if message_id is not None:
        if message_id:
            message = (await db.execute(select(Message).where(Message.id == message_id))).scalar_one_or_none()
            if not message:
                raise HTTPException(404, "Message not found")
        file.message_id = message_id  # can be None (detach)
    if status:
        file.status = status
    await db.commit()

    result = await db.execute(
        select(File)
        .where(File.id == file.id)
        .options(
            selectinload(File.user),
            selectinload(File.conversation),
            selectinload(File.message),
        )
    )

    file = result.scalar_one()
    return file

async def delete_file(db: AsyncSession, file_id: UUID) -> None:
    file = await get_file(db, file_id)
    await db.delete(file)
    await db.commit()

async def validate_and_save_file_to_storage(file: UploadFile, base_path: str = "uploads/"):
    os.makedirs(base_path, exist_ok=True)

    original_filename = os.path.basename(file.filename or "")
    if not original_filename or "." not in original_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = original_filename.split(".")[-1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file.filename}")
    unique_name = f"{str(uuid.uuid4())}_{original_filename}"
    file_path = os.path.join(base_path, unique_name)
    content = await file.read()
    if len(content) > 7 * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large: {file.filename}. File size should not exceed 7 MB.")
    await anyio.to_thread.run_sync(_write_file_content, file_path, content)
    return file_path, len(content)
