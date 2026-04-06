from pydantic import BaseModel
from typing import List, Optional

class ImportMessage(BaseModel):
    role: str
    content: str

class ImportConversationRequest(BaseModel):
    messages: List[ImportMessage]
    convo_metadata: Optional[dict] = None
