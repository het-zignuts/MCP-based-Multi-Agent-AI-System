from abc import ABC, abstractmethod
import logging

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.agent_layer.schemas import AgentContext, AgentResponse

from google.genai.types import Content, Part

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    ADK-backed base agent wrapper.
    Each agent internally uses ADK LlmAgent + Runner.
    """

    name: str
    description: str = ""

    def __init__(self):
        # ADK session system (can later be replaced with DB-backed session service)
        self.session_service = InMemorySessionService()

        # each agent must define its own ADK LlmAgent
        self.adk_agent: LlmAgent = self._build_adk_agent()

        from app.core.config import settings
        if settings.AGENT_MODEL:
            self.adk_agent.model = settings.AGENT_MODEL

        self.runner = Runner(
            agent=self.adk_agent,
            session_service=self.session_service,
            app_name="agent_system",
        )

    @abstractmethod
    def _build_adk_agent(self) -> LlmAgent:
        """
        Each agent defines:
        - model
        - instruction
        - tools (later MCP)
        """
        pass

    @abstractmethod
    def build_prompt(self, context: AgentContext) -> str:
        """
        Converts your unified memory context → final prompt string
        """
        pass

    def _compile_system_instruction(self, base_instruction: str, context: AgentContext) -> str:
        """
        Dynamically injects massive context into the System Prompt.
        This prevents ADK from duplicating the context in its chat history on every turn.
        """
        return f"""
{base_instruction}

--- BACKGROUND CONTEXT (Do not explicitly mention this context unless relevant) ---

MEMORY (STM):
{context.stm_context}

LONG TERM MEMORY (LTM):
{context.ltm_context}

USER PROFILE:
{context.profile_context}

RAG CONTEXT:
{context.rag_context}

CONVERSATION METADATA:
{context.conversation_metadata}
"""

    def _is_quota_error(self, exc: Exception) -> bool:
        """Returns True if the exception is a 429 / RESOURCE_EXHAUSTED quota error."""
        exc_str = str(exc).lower()
        return "429" in exc_str or "resource_exhausted" in exc_str or "quota" in exc_str

    async def _run_with_model(self, context: AgentContext, prompt: str) -> str:
        """Execute the ADK runner and collect the final response text."""
        from time import perf_counter
        started_at = perf_counter()
        model_name = getattr(self.adk_agent, "model", "unknown")
        logger.info(
            "Agent run START | agent=%s | model=%s | user_id=%s | conversation_id=%s | prompt_chars=%d",
            self.name, model_name, context.user_id, context.conversation_id, len(prompt),
        )

        # Ensure session exists
        session = None
        try:
            session = await self.session_service.get_session(
                app_name="agent_system",
                user_id=context.user_id,
                session_id=context.conversation_id
            )
        except Exception:
            pass

        if session is None:
            await self.session_service.create_session(
                app_name="agent_system",
                user_id=context.user_id,
                session_id=context.conversation_id
            )

        response_events = self.runner.run(
            user_id=context.user_id,
            session_id=context.conversation_id,
            new_message=Content(
                role="user",
                parts=[Part.from_text(text=prompt)]
            )
        )

        # Extract text from each Part in the Content object.
        # Do NOT use str(event.content) — that serialises the raw Content
        # object and leaks internal repr like "parts=[Part(...)] role='model'".
        final_text = ""
        for event in response_events:
            if hasattr(event, "content") and event.content:
                content = event.content
                if hasattr(content, "parts") and content.parts:
                    for part in content.parts:
                        text = getattr(part, "text", None)
                        if text:
                            final_text += text

        duration_s = round(perf_counter() - started_at, 3)
        logger.info(
            "Agent run END | agent=%s | model=%s | duration_s=%s | response_chars=%d",
            self.name, model_name, duration_s, len(final_text),
        )
        return final_text

    async def run(self, context: AgentContext) -> AgentResponse:
        from app.core.config import settings

        prompt = self.build_prompt(context)

        # Dynamically inject context into the System Instruction for this turn.
        # Use an instruction provider so ADK does not attempt default session
        # state placeholder injection on our compiled prompt text.
        base_instruction = self._build_adk_agent().instruction
        compiled_instruction = self._compile_system_instruction(
            base_instruction,
            context,
        )
        self.adk_agent.instruction = (
            lambda _ctx, compiled_instruction=compiled_instruction: compiled_instruction
        )

        logger.info(
            "Agent dispatch | agent=%s | model=%s | selected_agent=%s",
            self.name,
            getattr(self.adk_agent, "model", "unknown"),
            context.selected_agent,
        )

        try:
            final_text = await self._run_with_model(context, prompt)
        except Exception as primary_exc:
            if self._is_quota_error(primary_exc) and settings.AGENT_FALLBACK_MODEL:
                primary_model = self.adk_agent.model
                logger.warning(
                    "Agent '%s' hit quota limit on model '%s'. Falling back to '%s'. error=%s",
                    self.name, primary_model, settings.AGENT_FALLBACK_MODEL, primary_exc,
                )
                self.adk_agent.model = settings.AGENT_FALLBACK_MODEL
                try:
                    final_text = await self._run_with_model(context, prompt)
                finally:
                    # Always restore the primary model after the fallback attempt
                    self.adk_agent.model = primary_model
            else:
                raise

        return AgentResponse(
            content=final_text.strip(),
            agent_name=self.name,
            selected_agent=context.selected_agent,
        )