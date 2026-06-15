import asyncio

from app.agent_layer.schemas import AgentContext
from app.agent_layer.agents import RootAgent


async def main():
    context = AgentContext(
        user_id="1",
        conversation_id="1",
        user_message="How is the ideal weather in India?"
    )

    root = RootAgent()

    response = await root.run(context)

    print(response)


asyncio.run(main())