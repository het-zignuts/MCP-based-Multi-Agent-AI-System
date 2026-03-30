from pydantic import BaseModel
from typing import List

class ImportMessage(BaseModel):
    role: str
    content: str

class ImportConversationRequest(BaseModel):
    messages: List[ImportMessage]