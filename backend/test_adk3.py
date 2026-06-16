import asyncio
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.types import Message, TextPart
import os

os.environ["GROQ_API_KEY"] = "GROQ_API_KEY_REMOVED"

async def main():
    adk_agent = LlmAgent(
        name="document",
        model="groq/llama-3.1-70b",
        instruction="You are an expert Document Analyst Assistant."
    )
    runner = Runner(
        agent=adk_agent,
        session_service=InMemorySessionService(),
        app_name="agent_system",
    )
    response_events = runner.run(
        user_id="test",
        session_id="test",
        new_message=Message(role="user", parts=[TextPart(text="Hello, how are you?")])
    )
    final_text = ""
    for event in response_events:
        if hasattr(event, "content") and event.content:
            final_text += str(event.content)
    print("Final text:", final_text)

asyncio.run(main())
