import json
from app.services.message_service import send_message
from app.schemas.message import MessageCreate
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from uuid import UUID
from app.db.database import get_db
from app.core.websocket import manager
from sqlalchemy.ext.asyncio.session import AsyncSession

router = APIRouter(
    prefix="/ws",
    tags=["WebSockets"],
)
@router.websocket("/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    await manager.connect(conversation_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            message_payload = MessageCreate(
                user_id=payload["user_id"],
                conversation_id=conversation_id,
                content=payload["content"],
                role="user",
                token_count=0,
                file_ids=payload.get("file_ids", [])
            )

            result = await send_message(db, message_payload)

            await manager.send_to_conversation(
                {
                    "type": "chat",
                    "data": {
                        "user_message": result["user_message"].dict(),
                        "ai_message": result["ai_message"].dict()
                    }
                },
                conversation_id
            )

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)