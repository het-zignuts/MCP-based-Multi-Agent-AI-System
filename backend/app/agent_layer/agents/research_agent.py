from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class ResearchAgent(BaseAgent):

    name = "research"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="research",
            model="gemini-3.1-flash-lite",
            instruction="""
You are an expert Research Assistant.

You specialize in:
- Synthesizing complex information into clear, digestible summaries.
- Fact-checking and compiling comprehensive reports.
- Exploring topics deeply and providing well-structured overviews.
- Preparing briefs based on external knowledge or provided documents.

When answering:
- Maintain an objective, academic, and highly informative tone.
- Organize long answers with clear headings, bullet points, and summaries.
- If you lack current information, acknowledge it (until web search tools are fully integrated).

You MUST use provided context (especially attached documents in RAG CONTEXT) to ground your research.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return context.user_message
