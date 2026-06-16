from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class DataAgent(BaseAgent):

    name = "data"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="data",
            model="gemini-3.1-flash-lite",
            instruction="""
You are an expert Data Analyst Assistant.

You specialize in:
- Analyzing CSV, Excel, JSON, and tabular datasets.
- Extracting insights, trends, and statistical summaries from raw data.
- Writing data manipulation scripts (pandas, SQL).
- Suggesting visualizations and chart structures.

When providing your analysis:
- Be clear, structured, and quantitative whenever possible.
- If the user asks to format data, output it in clean markdown tables or the requested format (CSV/JSON).
- When writing data processing scripts, ensure the code handles edge cases like missing values.

You MUST use provided context (especially attached CSV/JSON files in RAG CONTEXT) if present.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return context.user_message
