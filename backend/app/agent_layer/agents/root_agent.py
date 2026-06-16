from app.agent_layer.schemas import AgentContext, AgentResponse
from app.agent_layer.core import agent_registry
from app.agent_layer.core.selector import AgentSelector
from app.agent_layer.agents.general_agent import GeneralAgent
from app.agent_layer.agents.code_agent import CodeAgent
from app.agent_layer.agents.data_agent import DataAgent
from app.agent_layer.agents.research_agent import ResearchAgent
from app.agent_layer.agents.document_agent import DocumentAgent
from app.agent_layer.agents.image_agent import ImageAgent
import logging

logger = logging.getLogger(__name__)                                               

class RootAgent:

    VALID_AGENTS = {"general", "code", "research", "data", "document", "image"}

    def __init__(self):
        # ensure all agents are registered
        if not agent_registry.exists("general"):
            agent_registry.register(GeneralAgent())
        if not agent_registry.exists("code"):
            agent_registry.register(CodeAgent())
        if not agent_registry.exists("data"):
            agent_registry.register(DataAgent())
        if not agent_registry.exists("research"):
            agent_registry.register(ResearchAgent())
        if not agent_registry.exists("document"):
            agent_registry.register(DocumentAgent())
        if not agent_registry.exists("image"):
            agent_registry.register(ImageAgent())

    async def run(self, context: AgentContext) -> AgentResponse:

        # Trust the explicit agent selection from the frontend (@mention).
        # Only fall back to LLM routing if no agent was explicitly chosen.
        if context.selected_agent and context.selected_agent in self.VALID_AGENTS:
            selected = context.selected_agent
            logger.info("Agent selection | mode=explicit | agent=%s", selected)
        else:
            # LLM supervisor routing: infer the best agent from the message content.
            # Pass "general" as the baseline hint if there's no prior agent context.
            from app.agent_layer.core.state import get_agent_state
            agent_state = get_agent_state(context.conversation_metadata)
            previous_agent = agent_state.get("active_agent", "general")
            logger.info(
                "Agent selection | mode=llm_routing | previous_agent=%s | message_preview=%s",
                previous_agent,
                context.user_message[:80],
            )
            selected = await AgentSelector.select_agent(
                context.user_message,
                previous_agent
            )
            logger.info("Agent selection | mode=llm_routing | resolved=%s", selected)

        # Ensure the resolved agent is registered and valid
        if not agent_registry.exists(selected) or selected not in self.VALID_AGENTS:
            logger.warning("Agent '%s' not found in registry, falling back to general", selected)
            selected = "general"
        logger.info("Agent selection | final=%s", selected)
        agent = agent_registry.get(selected)
        context.selected_agent = selected

        return await agent.run(context)