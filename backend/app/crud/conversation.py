from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from uuid import UUID
from datetime import datetime

from app.db.models import Conversation, User, Message
from app.schemas.conversation import ConversationRead

async def create_conversation(db: AsyncSession, payload: ConversationRead) -> Conversation:
    result = await db.execute(select(User).where(User.id == payload.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conversation = Conversation(
        title=payload.title,
        user_id=payload.user_id,
        convo_metadata=payload.convo_metadata
    )

    db.add(conversation)
    await db.commit()

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation.id)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.files),
            selectinload(Conversation.user)
        )
    )
    conversation = result.scalar_one()

    return conversation

async def get_conversation(db: AsyncSession, conversation_id: UUID) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id).options(
            selectinload(Conversation.files),
            selectinload(Conversation.user),
            selectinload(Conversation.messages).selectinload(Message.files)
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

async def get_conversations(db: AsyncSession, user_id: UUID | None = None) -> list[Conversation]:
    query = select(Conversation).options(
        selectinload(Conversation.files),
        selectinload(Conversation.user),
        selectinload(Conversation.messages).selectinload(Message.files)  
    )

    if user_id:
        query = query.where(Conversation.user_id == user_id)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return conversations

async def update_conversation(db: AsyncSession, conversation_id: UUID, title: str | None = None, convo_metadata: dict | None = None) -> Conversation:
    conversation = await get_conversation(db, conversation_id)
    if title is not None:
        conversation.title = title
    if convo_metadata is not None:
        conversation.convo_metadata = convo_metadata
    conversation.updated_at = datetime.utcnow()
    await db.commit()

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation.id)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.files),
            selectinload(Conversation.user)
        )
    )
    conversation = result.scalar_one()

    return conversation


async def update_conversation_metadata(
    db: AsyncSession,
    conversation_id: UUID,
    convo_metadata: dict,
) -> Conversation:
    return await update_conversation(
        db,
        conversation_id,
        convo_metadata=convo_metadata,
    )

async def delete_conversation(db: AsyncSession, conversation_id: UUID) -> None:
    conversation = await get_conversation(db, conversation_id)
    await db.delete(conversation)
    await db.commit()
