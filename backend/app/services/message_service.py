from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.db.models import Message, Conversation
from app.schemas.message import MessageCreate
from app.crud.message import create_message
from app.services.llm_service import get_llm_response_async
from app.services.rag.retriever import retrieve_pipeline

def build_message_history(
    messages: list[Message],
    rag_context: str = "",
) -> list[dict[str, str]]:
    history = []
    for message in messages:
        attached_files = getattr(message, "files", []) or []
        file_lines = [
            f"- {file.filename} ({file.status})"
            for file in attached_files
        ]
        file_block = ""
        if file_lines:
            file_block = "\n\nAttached files:\n" + "\n".join(file_lines)

        history.append(
            {
                "role": message.role,
                "content": f"{message.content}{file_block}",
            }
        )
    print("Context:", rag_context)
    if rag_context and history:
        last_message = history[-1]
        history[-1] = {
            **last_message,
            "content": (
                f"{last_message['content']}\n\n"
                f"Relevant context:\n{rag_context}"
            ),
        }

    return history

async def generate_ai_response(
    messages: list[Message],
    rag_context: str = "",
) -> str:
    history = build_message_history(messages, rag_context=rag_context)
    response = await get_llm_response_async(history)
    return response


async def fetch_conversation_history(
    db: AsyncSession,
    conversation_id,
    limit: int = 10,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .options(
            selectinload(Message.user),
            selectinload(Message.files),
        )
    )
    return list(reversed(result.scalars().all()))


def build_ai_message_payload(
    user_message: Message,
    ai_content: str,
    file_ids: list | None = None,
) -> MessageCreate:
    return MessageCreate(
        user_id=user_message.user_id,
        conversation_id=user_message.conversation_id,
        content=ai_content,
        role="assistant",
        token_count=None,
        file_ids=file_ids or [],
    )

async def send_message(
    db: AsyncSession,
    payload: MessageCreate,
    rag_context: str = "",
):
    # Save user message
    user_message = await create_message(db, payload)

    #  Fetch last N messages (context)
    messages = await fetch_conversation_history(db, payload.conversation_id)

    # Generate AI response
    ai_content = await generate_ai_response(messages, rag_context=rag_context)

    # Save AI message
    ai_message = build_ai_message_payload(
        user_message,
        ai_content,
        file_ids=payload.file_ids,
    )
    ai_message = await create_message(db, ai_message)

    return {
        "user_message": user_message,
        "ai_message": ai_message
    }


async def send_message_from_payload(
    db: AsyncSession,
    conversation_id,
    payload: dict,
    authenticated_user_id,
):
    message_payload = MessageCreate(
        user_id=authenticated_user_id,
        conversation_id=conversation_id,
        content=payload["content"],
        role="user",
        token_count=0,
        file_ids=payload.get("file_ids", []),
    )
    print('File IDs:', message_payload.file_ids)
    rag_context = await retrieve_pipeline(
        payload["content"],
        message_payload.file_ids or [],
        conversation_id,    
        authenticated_user_id,
        db,
    )
    print('Retrieved context:', rag_context)
    return await send_message(
        db,
        message_payload,
        rag_context=rag_context,
    )
