# inspect_agent_methods.py

import inspect

from google.adk.agents import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are helpful."
)

# print(dir(agent))
print(inspect.signature(agent.run))
print(inspect.signature(agent.run_async))