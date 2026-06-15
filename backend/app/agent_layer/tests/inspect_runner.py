from google.adk.runners import Runner
import inspect

# print(Runner)
# print(inspect.signature(Runner))
# print(dir(Runner))

print(inspect.signature(Runner.run))
print(inspect.signature(Runner.run_async))