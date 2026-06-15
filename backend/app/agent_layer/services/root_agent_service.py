from app.agent_layer.core.registry import AgentRegistry

from app.agent_layer.agents.general_agent import (
    GeneralAgent,
)

from app.agent_layer.agents.root_agent import (
    RootAgent,
)


class RootAgentService:

    def __init__(self):

        self.registry = AgentRegistry()

        self.registry.register(
            GeneralAgent()
        )

        # self.registry.register(
        #     RootAgent()
        # )

    def get_agent(
        self,
        name: str,
    ):
        return self.registry.get(name)

    def list_agents(
        self,
    ):
        return self.registry.list_agents()