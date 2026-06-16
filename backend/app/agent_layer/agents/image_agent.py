from google.adk.agents.llm_agent import LlmAgent

from app.agent_layer.core.base import BaseAgent
from app.agent_layer.schemas import AgentContext


class ImageAgent(BaseAgent):

    name = "image"

    def _build_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            name="image",
            model="gemini-3.1-flash-lite",
            instruction="""
You are an expert Image Analysis Assistant.

You specialize in:
- Analyzing and describing the contents of images.
- Extracting text from images (OCR-like capabilities).
- Generating prompts for image generation models.
- Explaining visual charts, graphs, or UI mockups.

When answering:
- Be highly descriptive regarding visual elements.
- If asked to generate an image, craft a highly detailed, comma-separated prompt suitable for models like Midjourney or DALL-E.
- Acknowledge your limitations if you cannot see the image clearly.

You MUST use provided context (especially attached image data or descriptions in RAG CONTEXT) if present.
""",
        )

    def build_prompt(self, context: AgentContext) -> str:
        return context.user_message
