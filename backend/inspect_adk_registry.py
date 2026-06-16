from google.adk.models.registry import _llm_registry_dict, LLMRegistry

for pattern in _llm_registry_dict.keys():
    print(pattern)
