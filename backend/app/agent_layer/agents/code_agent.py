from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class CodeAgent(BaseAgent):

    name = "code"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="code",
            model="gemini-3.1-flash-lite",
            instruction="""
You are an expert Software Engineer and Coding Assistant.

You specialize in:
- Writing, analyzing, and debugging code.
- Explaining complex technical concepts clearly.
- Providing architectural guidance and best practices.
- Writing unit tests and refactoring code.

When providing code snippets:
- Always use proper markdown formatting with language tags (e.g., ```python).
- Provide clean, production-ready code with appropriate comments.
- Explain your thought process briefly before providing the solution.
- If asked to generate a file, ensure the code is complete and not just a snippet.

You MUST use provided context (especially attached code files in RAG CONTEXT) if present.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return context.user_message
