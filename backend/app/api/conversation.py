from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID

from app.schemas.conversation import ConversationCreate, ConversationRead
from app.crud.conversation import *
from app.db.database import get_db
from app.services.conversation.history_service import fetch_conversation_history
from app.schemas.import_convo import ImportConversationRequest
from app.schemas.message import MessageCreate
from app.crud.message import create_message

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.post("/", response_model=ConversationRead)
async def create(payload: ConversationCreate, db: AsyncSession = Depends(get_db)):
    try:
        conversation = await create_conversation(db, payload)
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
async def update(conversation_id: UUID, title: str, convo_metadata: dict, db: AsyncSession = Depends(get_db)):
    try:
        conversation = await get_conversation(db, conversation_id)
        updated_conversation = await update_conversation(db, conversation_id, title=title, convo_metadata=convo_metadata)
        return updated_conversation
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{conversation_id}")
async def delete(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await delete_conversation(db, conversation_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.get("/{conversation_id}/export")
async def export_conversation_api(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, conversation_id)
    messages = await fetch_conversation_history(db, conversation_id, limit=1000)

    return {
        "convo_metadata": conversation.convo_metadata,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }

@router.post("/{conversation_id}/import")
async def import_conversation_api(
    conversation_id: UUID,
    payload: ImportConversationRequest,
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, conversation_id)
    if payload.convo_metadata is not None:
        conversation.convo_metadata = payload.convo_metadata
        await db.commit()

    for msg in payload.messages:
        await create_message(
            db,
            MessageCreate(
                conversation_id=conversation_id,
                role=msg.role,
                content=msg.content,
                user_id=conversation.user_id,
                token_count=0,
                file_ids=[],
            ),
        )

    return {"status": "imported"}
