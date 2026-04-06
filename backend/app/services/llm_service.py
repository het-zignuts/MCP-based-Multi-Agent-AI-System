import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from loguru import logger
from openai import OpenAI
from groq import Groq

from app.core.config import settings

LLM_EXECUTOR = ThreadPoolExecutor(max_workers=4)
atexit.register(lambda: LLM_EXECUTOR.shutdown(wait=False))
SYSTEM_PROMPT = """You are a helpful AI assistant for a multi-agent AI system.

Answer clearly, directly, and truthfully.
Use the provided conversation history and retrieved context when they are relevant.
If the context is missing, incomplete, or not enough to answer safely, say that plainly instead of making things up.
When files are attached, treat them as user-provided materials and rely on the retrieved context derived from them when available.
Continue the conversation naturally instead of describing what the user appears to be doing.
Avoid meta-analysis such as "the user's message seems to..." unless the user explicitly asks for that.
When the user gives a short follow-up like "so", "and?", or "continue", infer the most natural continuation from the recent conversation.
Treat explicit facts, titles, names, and identifiers provided by the user as the current working context unless the user asks you to verify or correct them.
If the user's request includes a quoted passage, excerpt, snippet, or other bounded material, focus on analyzing that provided material instead of re-identifying or replacing it.
If you are uncertain, ask a brief clarifying question instead of guessing repeatedly or repeatedly correcting yourself.
Do not loop through multiple conflicting answers. Give the best grounded answer once.
"""

_groq_client = None
_gemini_client = None


def get_groq_client():
    global _groq_client

    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)

    return _groq_client


def get_gemini_client():
    global _gemini_client

    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")
        _gemini_client = OpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    return _gemini_client


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


def _serialize_prompt_for_logs(messages: list[dict[str, str]]) -> str:
    try:
        return json.dumps(messages, ensure_ascii=True)
    except Exception:
        return str(messages)

def get_llm_response(prompt):
    if not settings.MODEL:
        raise ValueError("MODEL is not configured.")

    messages = build_llm_messages(prompt)
    logger.info(
        "LLM request | model={} | temperature={} | messages={}",
        settings.MODEL,
        settings.LLM_TEMPERATURE,
        _serialize_prompt_for_logs(messages),
    )

    model_name = settings.MODEL.strip()
    if model_name.startswith("gemini"):
        client = get_gemini_client()
    else:
        client = get_groq_client()

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        reasoning_format="hidden",
        reasoning_effort="none",
    )
    content = response.choices[0].message.content
    logger.info("LLM response | content={}", (content or "").strip())
    return (content or "").strip()

async def get_llm_response_async(prompt):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(LLM_EXECUTOR, get_llm_response, prompt)
