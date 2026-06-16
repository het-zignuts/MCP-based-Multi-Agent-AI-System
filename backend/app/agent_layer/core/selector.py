from app.agent_layer.core import agent_registry
from app.services.llm import llm
from pydantic import BaseModel, Field
from loguru import logger

class AgentSelection(BaseModel):
    selected_agent: str = Field(description="The name of the agent to select (general, code, research, data, document, image)")
    reason: str = Field(description="Why this agent was selected")

class AgentSelector:

    @staticmethod
    async def select_agent(message: str, current_agent: str) -> str:
        prompt = f"""
You are an expert intent router for a multi-agent system.
Your job is to read the user's message and determine if the current agent should handle it, or if it needs to be routed to a specialized agent.

Available agents:
- general: For general chat, fallback queries, and normal conversation.
- code: For python, coding, debugging, API design, etc.
- research: For searching the web, getting news, fact finding.
- data: For CSV, excel, datasets, analysis.
- document: For PDF, word documents, reading reports.
- image: For understanding or generating images.

Current active agent: {current_agent}
User message: {message}

If the user message is a continuation of the previous thought, stick with the '{current_agent}' agent. Only switch agents if the user is explicitly asking for a new type of task.
Select the best agent from the available list.

OUTPUT FORMAT:
You must return ONLY a JSON object that matches this schema:
{{
  "selected_agent": "general" | "code" | "research" | "data" | "document" | "image",
  "reason": "a brief explanation of why this agent was selected"
}}
"""
        try:
            decision = await llm.structured(
                messages=[{"role": "user", "content": prompt}],
                purpose="agent_routing",
                response_model=AgentSelection,
            )
            logger.info("LLM agent routing decided | selected={} | reason={}", decision.selected_agent, decision.reason)
            return decision.selected_agent.lower()
        except Exception as e:
            logger.exception("LLM agent routing failed, falling back to current agent.")
            return current_agent