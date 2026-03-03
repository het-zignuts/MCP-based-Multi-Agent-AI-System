from fastapi import APIRouter, WebSocket
from app.core.websocket import manager

router=APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(int(user_id), websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Echo: {data}", int(user_id))
    except:
        manager.disconnect(int(user_id))