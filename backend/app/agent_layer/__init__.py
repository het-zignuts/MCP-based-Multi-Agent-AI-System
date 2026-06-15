from app.agent_layer.services.root_agent_service import (
    RootAgentService,
)
from app.agent_layer.agents.general_agent import GeneralAgent
from app.agent_layer.core import agent_registry

root_agent_service = RootAgentService()

# agent_registry.register("general", GeneralAgent())
agent_registry.register(GeneralAgent())