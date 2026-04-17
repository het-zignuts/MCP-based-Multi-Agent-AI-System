import json
from typing import Any

from app.services.llm_service import get_llm_response_async


CONVERSATION_METADATA_PROMPT = """
You extract compact conversation metadata for memory and retrieval.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Return this exact shape:
{
  "topics": ["..."],
  "entities": ["..."],
  "active_goals": ["..."],
  "sentiment": "neutral",
  "summary_hint": "..."
}

Rules:
- topics: short topic labels
- entities: important people, products, projects, songs, places, tools, or named concepts
- active_goals: only goals/tasks that are active in the CURRENT conversation focus right now
- sentiment: one of "positive", "neutral", "negative", "mixed"
- summary_hint: 1 short sentence about the current conversation focus
- If a field has no useful value, return an empty list or "neutral" or "".
- Do not invent facts.
- Do not carry forward superseded or unrelated goals from earlier parts of the conversation.
- Do not encode recurring answer formats, stylistic quirks, games, or temporary reply patterns as active_goals unless the user is clearly still pursuing them right now.
"""


async def extract_conversation_metadata(conversation_text: str) -> dict[str, Any]:
    if not conversation_text.strip():
        return {
            "topics": [],
            "entities": [],
            "active_goals": [],
            "sentiment": "neutral",
            "summary_hint": "",
        }

    prompt = f"""
{CONVERSATION_METADATA_PROMPT}

Conversation:
\"\"\"
{conversation_text}
\"\"\"
"""

    response = await get_llm_response_async([
        {"role": "user", "content": prompt}
    ], purpose="conversation_metadata_extraction")

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return {
            "topics": [],
            "entities": [],
            "active_goals": [],
            "sentiment": "neutral",
            "summary_hint": "",
        }

    topics = parsed.get("topics", [])
    entities = parsed.get("entities", [])
    active_goals = parsed.get("active_goals", [])
    sentiment = parsed.get("sentiment", "neutral")
    summary_hint = parsed.get("summary_hint", "")

    if not isinstance(topics, list):
        topics = []
    if not isinstance(entities, list):
        entities = []
    if not isinstance(active_goals, list):
        active_goals = []
    if not isinstance(sentiment, str):
        sentiment = "neutral"
    if not isinstance(summary_hint, str):
        summary_hint = ""

    valid_sentiments = {"positive", "neutral", "negative", "mixed"}
    if sentiment not in valid_sentiments:
        sentiment = "neutral"

    return {
        "topics": [str(item).strip() for item in topics if str(item).strip()],
        "entities": [str(item).strip() for item in entities if str(item).strip()],
        "active_goals": [str(item).strip() for item in active_goals if str(item).strip()],
        "sentiment": sentiment,
        "summary_hint": summary_hint.strip(),
    }
