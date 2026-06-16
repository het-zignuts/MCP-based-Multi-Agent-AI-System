from pydantic import BaseModel, Field
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

    # The agent to route to. If set by the frontend (@mention), it bypasses LLM routing.
    # If None, the LLM selector picks the best agent.
    selected_agent: Optional[str] = Field(
        default=None,
        description="Explicitly selected agent from the frontend @mention. Overrides LLM routing when set."
    )


class AgentResponse(BaseModel):
    selected_agent: Optional[str] = None   # Echo back the agent chosen for this turn
    agent_name: str
    content: Optional[str] = None  # LLM output content


class AgentState(BaseModel):
    active_agent: str = "general"
    last_agent: str | None = None