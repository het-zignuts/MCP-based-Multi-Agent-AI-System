import asyncio
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import os

os.environ["GROQ_API_KEY"] = "GROQ_API_KEY_REMOVED"

async def main():
    adk_agent = LlmAgent(
        name="document",
        model="groq/llama-3.3-70b-versatile",
        instruction="You are an expert Document Analyst Assistant."
    )
    ss = InMemorySessionService()
    await ss.create_session(app_name="agent_system", user_id="test", session_id="test")
    runner = Runner(
        agent=adk_agent,
        session_service=ss,
        app_name="agent_system",
    )
    response_events = runner.run(
        user_id="test",
        session_id="test",
        new_message=Content(role="user", parts=[Part.from_text(text="Hello")])
    )
    final_text = ""
    for event in response_events:
        if hasattr(event, "content") and event.content:
            final_text += str(event.content)
    print("Final text:", final_text)

asyncio.run(main())
