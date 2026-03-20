from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.message import MessageCreate
from app.services.message_service import send_message
from app.db.database import get_db

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/send")
async def chat(payload: MessageCreate, db: AsyncSession = Depends(get_db)):
    return await send_message(db, payload)