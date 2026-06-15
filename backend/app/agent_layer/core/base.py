from abc import ABC, abstractmethod
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.agent_layer.schemas import AgentContext, AgentResponse


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

    async def run(self, context: AgentContext) -> AgentResponse:
        prompt = self.build_prompt(context)

        response_events = self.runner.run(
            user_id=context.user_id,
            session_id=context.conversation_id,
            new_message={
                "role": "user",
                "parts": [{"text": prompt}]
            }
        )

        final_text = ""
        for event in response_events:
            if hasattr(event, "content") and event.content:
                final_text += str(event.content)

        return AgentResponse(
            content=final_text.strip(),
            agent_name=self.name,
        )