from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    user_id: int
    conversation_id: Optional[int] = None
    message: str

class ChatResponse(BaseModel):
    conversation_id: int
    reply: str