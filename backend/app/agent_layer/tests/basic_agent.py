from google.adk.agents import Agent

root_agent = Agent(
    name="assistant",
    model="gemini-3.1-flash-lite",
    description="Simple assistant",
    instruction="You are a helpful assistant."
)

# print(root_agent)

print(type(root_agent))
print(root_agent.name)
print(root_agent.description)