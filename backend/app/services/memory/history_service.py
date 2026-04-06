from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.db.models import Message


async def fetch_conversation_history(
    db: AsyncSession,
    conversation_id,
    limit: int | None = 200,
) -> list[Message]:
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .options(
            selectinload(Message.user),
            selectinload(Message.files),
        )
    )

    if limit is not None:
        query = query.limit(limit)

    result = await db.execute(query)
    return list(reversed(result.scalars().all()))
