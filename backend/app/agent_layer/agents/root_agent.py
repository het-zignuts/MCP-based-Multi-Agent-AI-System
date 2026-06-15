from app.agent_layer.schemas import AgentContext, AgentResponse
from app.agent_layer.core import agent_registry
from app.agent_layer.core.selector import AgentSelector
from app.agent_layer.agents.general_agent import GeneralAgent


class RootAgent:

    VALID_AGENTS = {"general", "code", "research", "data", "document", "image"}

    def __init__(self):
        # ensure default agent exists
        if not agent_registry.exists("general"):
            agent_registry.register(GeneralAgent())

    async def run(self, context: AgentContext) -> AgentResponse:

        selected = AgentSelector.select_agent(context.user_message)

        if not agent_registry.exists(selected):
            selected = "general"

        if selected not in self.VALID_AGENTS:
            selected = "general"

        agent = agent_registry.get(selected)

        return await agent.run(context)