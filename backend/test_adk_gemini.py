import asyncio
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import os
from dotenv import load_dotenv

load_dotenv(".env")

async def main():
    adk_agent = LlmAgent(
        name="document",
        model="gemini-3.1-flash-lite",
        instruction="You are an expert Document Analyst Assistant."
    )
    
    session_service = InMemorySessionService()
    runner = Runner(
        agent=adk_agent,
        session_service=session_service,
        app_name="agent_system",
    )
    
    # Create the session explicitly first
    await session_service.create_session(
        app_name="agent_system",
        user_id="test",
        session_id="test"
    )
    
    new_msg = Content(
        role="user",
        parts=[Part.from_text(text="Hello, how are you?")]
    )
    
    response_events = runner.run(
        user_id="test",
        session_id="test",
        new_message=new_msg
    )
    final_text = ""
    for event in response_events:
        if hasattr(event, "content") and event.content:
            final_text += str(event.content)
    print("Final text:", final_text)

asyncio.run(main())
