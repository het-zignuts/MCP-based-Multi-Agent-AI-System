from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID

from app.schemas.conversation import ConversationCreate, ConversationRead
from app.crud.conversation import *
from app.db.database import get_db

router = APIRouter()

@router.post("/", response_model=ConversationRead)
async def create(payload: ConversationCreate, db: AsyncSession = Depends(get_db)):
    try:
        conversation = create_conversation(db, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return conversation

@router.get("/{conversation_id}", response_model=ConversationRead)
async def read(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        conversation = await get_conversation(db, conversation_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return conversation

@router.get("/", response_model=list[ConversationRead])
async def read_all(user_id:UUID, db: AsyncSession = Depends(get_db)):
    try:
        conversations = await get_conversations(db, user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return conversations

@router.put("/{conversation_id}")
async def update(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        conversation = await get_conversation(db, conversation_id)
        updated_conversation = await update_conversation(db, conversation_id, title=conversation.title, convo_metadata=conversation.convo_metadata)
        return updated_conversation
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{conversation_id}")
async def delete(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await delete_conversation(db, conversation_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))