from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class GeneralAgent(BaseAgent):

    name = "general"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="general",
            model="groq/llama-3.1-70b",  # or your configured model
            instruction="""
You are a General Assistant.

You handle:
- conversations
- explanations
- general reasoning
- fallback queries

You MUST use provided context if present.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return f"""
USER MESSAGE:
{context.user_message}

--- MEMORY (STM) ---
{context.stm_context}

--- LONG TERM MEMORY (LTM) ---
{context.ltm_context}

--- PROFILE ---
{context.profile_context}

--- RAG CONTEXT ---
{context.rag_context}

--- METADATA ---
{context.conversation_metadata}
"""