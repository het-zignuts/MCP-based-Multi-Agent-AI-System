from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import Conversation, Memory, User
from app.schemas.memory import MemoryCreate, MemoryUpdate


async def create_memory(db: AsyncSession, payload: MemoryCreate) -> Memory:
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.conversation_id is not None:
        conversation_result = await db.execute(
            select(Conversation).where(Conversation.id == payload.conversation_id)
        )
        conversation = conversation_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.user_id != payload.user_id:
            raise HTTPException(
                status_code=403,
                detail="Conversation does not belong to this user",
            )

    memory = Memory(**payload.model_dump())
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def get_memory(db: AsyncSession, memory_id: UUID) -> Memory:
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


async def get_memories_by_user(
    db: AsyncSession,
    user_id: UUID,
    memory_type: str | None = None,
    conversation_id: UUID | None = None,
    only_active: bool = True,
) -> list[Memory]:
    query = select(Memory).where(Memory.user_id == user_id)

    if only_active:
        query = query.where(Memory.is_active == True)

    if memory_type:
        query = query.where(Memory.memory_type == memory_type)

    if conversation_id:
        query = query.where(Memory.conversation_id == conversation_id)

    query = query.order_by(Memory.updated_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_memory(
    db: AsyncSession,
    memory_id: UUID,
    payload: MemoryUpdate,
) -> Memory:
    memory = await get_memory(db, memory_id)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(memory, key, value)

    memory.updated_at = datetime.utcnow()

    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def deactivate_memory(db: AsyncSession, memory_id: UUID) -> Memory:
    memory = await get_memory(db, memory_id)
    memory.is_active = False
    memory.updated_at = datetime.utcnow()

    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def delete_memory(db: AsyncSession, memory_id: UUID) -> None:
    memory = await get_memory(db, memory_id)
    await db.delete(memory)
    await db.commit()

async def touch_memory(
    db: AsyncSession,
    memory_id: UUID,
    *,
    content: str | None = None,
    memory_metadata: dict | None = None,
    importance_score: float | None = None,
    source: str | None = None,
    embedding: list[float] | None = None,
) -> Memory:
    memory = await get_memory(db, memory_id)

    if content is not None:
        memory.content = content
    if memory_metadata is not None:
        memory.memory_metadata = memory_metadata
    if importance_score is not None:
        memory.importance_score = importance_score
    if source is not None:
        memory.source = source
    if embedding is not None:
        memory.embedding = embedding

    memory.updated_at = datetime.utcnow()

    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory

async def get_recent_memories_by_type(
    db: AsyncSession,
    *,
    user_id: UUID,
    memory_type: str,
    limit: int = 10,
    only_active: bool = True,
) -> list[Memory]:
    query = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.memory_type == memory_type,
        )
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )

    if only_active:
        query = query.where(Memory.is_active == True)

    result = await db.execute(query)
    return list(result.scalars().all())
