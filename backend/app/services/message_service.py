from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.db.models import Message, Conversation
from app.schemas.message import MessageCreate
from app.crud.message import create_message
from app.services.llm_service import get_llm_response

async def generate_ai_response(messages: list[Message]) -> str:
    # simple placeholder
    history=[]
    for message in messages:
        history.append({"role": message.role, "content": message.content})
    response=get_llm_response(history)
    return response

async def send_message(db: AsyncSession, payload: MessageCreate):
    # Save user message
    user_message = await create_message(db, payload)

    #  Fetch last N messages (context)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == payload.conversation_id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .options(
            selectinload(Message.user),
            selectinload(Message.files),
        )
    )
    messages = list(reversed(result.scalars().all()))

    # Generate AI response
    ai_content = await generate_ai_response(messages)

    # Save AI message
    ai_message = MessageCreate(
        user_id=user_message.user_id,
        conversation_id=user_message.conversation_id,
        content=ai_content,
        role="assistant",
        token_count=len(ai_content.split()),
        file_ids=payload.file_ids
    )
    ai_message = await create_message(db, ai_message)

    return {
        "user_message": user_message,
        "ai_message": ai_message
    }