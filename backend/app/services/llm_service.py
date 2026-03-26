import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor

from groq import Groq

from app.core.config import settings

LLM_EXECUTOR = ThreadPoolExecutor(max_workers=4)
atexit.register(lambda: LLM_EXECUTOR.shutdown(wait=False))
SYSTEM_PROMPT = """You are a helpful AI assistant for a multi-agent AI system.

Answer clearly, directly, and truthfully.
Use the provided conversation history and retrieved context when they are relevant.
If the context is missing, incomplete, or not enough to answer safely, say that plainly instead of making things up.
When files are attached, treat them as user-provided materials and rely on the retrieved context derived from them when available.
"""

_groq_client = None


def get_groq_client():
    global _groq_client

    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)

    return _groq_client


def parse_latest_message(content: str) -> tuple[str, str, str]:
    context_marker = "\n\nRelevant context:\n"
    attachment_marker = "\n\nAttached files:\n"

    if context_marker in content:
        user_portion, context = content.split(context_marker, 1)
    else:
        user_portion = content
        context = ""

    if attachment_marker in user_portion:
        user_query, attached_files = user_portion.split(attachment_marker, 1)
    else:
        user_query = user_portion
        attached_files = ""

    return user_query.strip(), attached_files.strip(), context.strip()


def build_llm_messages(prompt: list[dict[str, str]]) -> list[dict[str, str]]:
    if not prompt:
        return [{"role": "system", "content": SYSTEM_PROMPT}]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for message in prompt[:-1]:
        messages.append(
            {
                "role": message["role"],
                "content": message["content"].strip(),
            }
        )

    user_query, attached_files, context = parse_latest_message(prompt[-1]["content"])

    final_sections = [f"User question:\n{user_query}"]
    if attached_files:
        final_sections.append(f"Attached files:\n{attached_files}")
    if context:
        final_sections.append(f"Relevant context:\n{context}")

    messages.append(
        {
            "role": prompt[-1]["role"],
            "content": "\n\n".join(final_sections),
        }
    )
    return messages

def get_llm_response(prompt):
    if not settings.MODEL:
        raise ValueError("MODEL is not configured.")

    client = get_groq_client()
    messages = build_llm_messages(prompt)
    response = client.chat.completions.create(
        model=settings.MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
    )
    content = response.choices[0].message.content
    return (content or "").strip()

async def get_llm_response_async(prompt):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(LLM_EXECUTOR, get_llm_response, prompt)
