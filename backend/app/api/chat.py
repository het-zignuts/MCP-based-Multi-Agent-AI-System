from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import llm_service
from app.core.database import get_session
from datetime import datetime

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session: Session = Depends(get_session)):
    user=get_user(request.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not request.conversation_id:
        conversation = create_conversation(user_id=request.user_id, session=session)
    else:
        conversation = get_conversation(request.conversation_id, session)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = create_message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
        token_count=len(request.message.split())
    )

    reply = await llm_service.generate(request.message)

    assistant_message = create_message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
        token_count=len(reply.split())
    )

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply
    )