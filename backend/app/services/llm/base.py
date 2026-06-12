from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseLLMService(ABC):

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        purpose: str = "chat_response",
    ) -> str:
        pass

    @abstractmethod
    async def structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        purpose: str,
    ) -> BaseModel:
        pass