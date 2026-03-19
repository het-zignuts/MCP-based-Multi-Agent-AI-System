from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List
from uuid import UUID

from app.schemas.message import MessageCreate, MessageRead
from app.crud.message import *
from app.db.database import get_db

router = APIRouter(prefix="/messages", tags=["Messages"])

@router.post("/", response_model=MessageRead)
async def create(payload: MessageCreate, db: AsyncSession = Depends(get_db)):
    try:
        message = await create_message(db, payload)
    except Exception as e:
        raise e
    return message

@router.get("/{message_id}", response_model=MessageRead)
async def read(message_id: str, db: AsyncSession = Depends(get_db)):
    try:
        message = await get_message(db, message_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return message

@router.get("/", response_model=List[MessageRead])
async def read_all(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        messages = await get_messages(db, conversation_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return messages

@router.put("/{message_id}")
async def update(message_id: UUID, file_ids: list[UUID] | None = None, content: str | None = None, db: AsyncSession = Depends(get_db)):
    try:
        updated_message = await update_message(db, message_id, content=content, file_ids=file_ids)
        return updated_message
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{message_id}")
async def delete(message_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await delete_message(db, message_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))