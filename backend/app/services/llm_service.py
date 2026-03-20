def get_llm_response(prompt):
    last_user_message = prompt[-1]["content"]
    return f"You said: {last_user_message}"