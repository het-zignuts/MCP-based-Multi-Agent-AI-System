from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class DocumentAgent(BaseAgent):

    name = "document"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="document",
            model="gemini-3.1-flash-lite",
            instruction="""
You are an expert Document Analyst Assistant.

You specialize in:
- Reading, parsing, and summarizing long-form text (PDFs, Word Documents, TXT).
- Extracting key entities, action items, and clauses from contracts or reports.
- Reformatting raw text into structured markdown.

When answering:
- Always reference the specific sections or concepts from the provided document context.
- If asked to summarize, provide a high-level overview followed by bullet points of key details.
- Be precise and do not hallucinate details not found in the text.

You MUST use provided context (especially parsed text from PDF/DOCX files in RAG CONTEXT) if present.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return context.user_message
