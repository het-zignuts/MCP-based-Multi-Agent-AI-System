# inspect_content.py

from google.genai import types
import inspect

print(types.Content)

print(inspect.signature(types.Content))