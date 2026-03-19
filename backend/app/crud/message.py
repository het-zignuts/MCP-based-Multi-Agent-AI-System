from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException
from sqlalchemy.orm import selectinload
from app.db.models import User, Conversation, Message, File
from uuid import UUID

from app.schemas import MessageCreate

async def create_message(session: AsyncSession, payload: MessageCreate):
    user=await session.execute(select(User).where(User.id==payload.user_id))
    user=user.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    conversation=await session.execute(select(Conversation).where(Conversation.id==payload.conversation_id))
    conversation=conversation.scalar_one_or_none()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    message=Message(**payload.dict())
    message.user=user
    message.conversation=conversation
    
    session.add(message)
    await session.flush()
    
    if payload.file_ids:
        files=await session.execute(select(File).where(File.id.in_(payload.file_ids)))
        files=files.scalars().all()
        if len(files) != len(payload.file_ids):
            raise HTTPException(status_code=404, detail="Some files not found")
        for file in files:
            if file.conversation_id != payload.conversation_id:
                raise HTTPException(status_code=400, detail="File does not belong to this conversation")
            file.message_id=message.id
        # remember to make early loading
    session.add(message)
    await session.commit()

    result = await session.execute(
        select(Message)
        .where(Message.id == message.id)
        .options(
            selectinload(Message.files),
            selectinload(Message.user),
            selectinload(Message.conversation),
        )
    )
    message = result.scalar_one()
    return message

async def get_message(db: AsyncSession, message_id: UUID) -> Message:
    message = await db.execute(select(Message).where(Message.id == message_id).options(selectinload(Message.files), selectinload(Message.user), selectinload(Message.conversation)))
    message = message.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

async def get_messages(db: AsyncSession, conversation_id: UUID | None = None) -> list[Message]:
    query = select(Message).options(
        selectinload(Message.files),
        selectinload(Message.user),
        selectinload(Message.conversation),
    )
    if conversation_id:
        query = query.where(Message.conversation_id == conversation_id)
    result = await db.execute(query)
    messages = result.scalars().all()
    return messages

async def update_message(db: AsyncSession, message_id: UUID, content: str | None = None, file_ids: list[UUID] | None = None) -> Message:
    message = await get_message(db, message_id)
    
    if content is not None:
        message.content = content

    if file_ids is not None:
        result = await db.execute(select(File).where(File.message_id == message.id))
        existing_files = result.scalars().all()
        for file in existing_files:
            file.message_id = None
        result = await db.execute(select(File).where(File.id.in_(file_ids)))
        new_files = result.scalars().all()

        if len(new_files) != len(file_ids):
            raise HTTPException(status_code=404, detail="Some files not found")

        for file in new_files:
            file.message_id = message.id

    await db.commit()

    result = await db.execute(
        select(Message)
        .where(Message.id == message.id)
        .options(
            selectinload(Message.files),
            selectinload(Message.user),
            selectinload(Message.conversation),
        )
    )

    message = result.scalar_one()
    return message

async def delete_message(db: AsyncSession, message_id: UUID) -> None:
    message = await get_message(db, message_id)
    result = await db.execute(
        select(File).where(File.message_id == message.id)
    )
    files = result.scalars().all()
    for file in files:
        file.message_id = None # detaching files, delete it later
    await db.delete(message)
    await db.commit()