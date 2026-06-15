from pydantic import BaseModel, Field


from pydantic import BaseModel
from typing import Optional, Dict


class AgentContext(BaseModel):
    user_id: str
    conversation_id: str
    user_message: str

    # MEMORY LAYER (your system)
    stm_context: str = ""
    ltm_context: str = ""
    profile_context: str = ""

    # RAG / FILE CONTEXT
    rag_context: str = ""

    # METADATA
    conversation_metadata: Dict = {}

    selected_agent: Optional[str] = Field(default=None, description="The agent selected to handle this message. Can be set by the selector tool or manually.")


class AgentResponse(BaseModel):
    content: str
    agent_name: str

class AgentState(BaseModel):
    active_agent: str = "general"
    last_agent: str | None = None
    mentioned_agent: str | None = None