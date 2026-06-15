from app.agent_layer.core.base import BaseAgent


class AgentRegistry:

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        if not hasattr(agent, "name"):
            raise ValueError(f"{agent} missing .name")

        self._agents[agent.name] = agent

    def get(self, agent_name: str) -> BaseAgent:
        agent = self._agents.get(agent_name)

        if not agent:
            raise ValueError(
                f"Agent '{agent_name}' not registered. "
                f"Available agents: {list(self._agents.keys())}"
            )

        return agent

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())
        
    def exists(self, agent_name: str) -> bool:
        return agent_name in self._agents
    
    def get_all(self) -> dict[str, BaseAgent]:
        return self._agents