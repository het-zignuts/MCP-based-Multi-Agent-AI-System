import json
import logging
from time import perf_counter
from  app.services.message.message_service import send_message_from_payload
from app.schemas.message import MessageRead
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import select
from uuid import UUID
from app.db.database import get_db
from app.db.models import Conversation
from app.core.websocket import manager
from  app.services.time.timing import elapsed_minutes
from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ws",
    tags=["WebSockets"],
)

@router.websocket("/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        await websocket.close(code=1008)
        return

    try:
        authenticated_user_id = UUID(user_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == authenticated_user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        await websocket.close(code=1008)
        return

    await manager.connect(conversation_id, websocket)

    try:
        while True:
            receive_started_at = perf_counter()
            data = await websocket.receive_text()
            logger.info(
                "WebSocket timing | stage=receive_text | conversation_id=%s | duration_min=%.4f",
                conversation_id,
                elapsed_minutes(receive_started_at),
            )
            try:
                payload = json.loads(data)
                process_started_at = perf_counter()
                result = await send_message_from_payload(
                    db,
                    conversation_id,
                    payload,
                    authenticated_user_id,
                )
                logger.info(
                    "WebSocket timing | stage=process_message | conversation_id=%s | duration_min=%.4f",
                    conversation_id,
                    elapsed_minutes(process_started_at),
                )

                send_started_at = perf_counter()
                await manager.send_to_conversation(
                    jsonable_encoder({
                        "type": "chat",
                        "data": {
                            "conversation_id": str(conversation_id),
                            "user_message": MessageRead.model_validate(
                                result["user_message"]
                            ).model_dump(),
                            "ai_message": MessageRead.model_validate(
                                result["ai_message"]
                            ).model_dump(),
                        }
                    }),
                    conversation_id
                )
                logger.info(
                    "WebSocket timing | stage=send_to_conversation | conversation_id=%s | duration_min=%.4f",
                    conversation_id,
                    elapsed_minutes(send_started_at),
                )
            except Exception:
                logger.exception(
                    "WebSocket message handling failed for conversation %s",
                    conversation_id,
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "Failed to process the message.",
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
