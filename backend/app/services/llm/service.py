from pydantic import BaseModel

from app.services.llm.base import BaseLLMService
from .llm_service import get_llm_response_async


class LLMService(BaseLLMService):

    async def chat(
        self,
        messages: list[dict[str, str]],
        purpose: str = "chat_response",
    ) -> str:
        return await get_llm_response_async(
            messages,
            purpose=purpose,
        )

    async def structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        purpose: str,
    ) -> BaseModel:
        response = await get_llm_response_async(
            messages,
            purpose=purpose,
            response_format={"type": "json_object"},
        )

        return response_model.model_validate_json(response)