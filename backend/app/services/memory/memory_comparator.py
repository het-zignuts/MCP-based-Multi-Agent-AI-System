import json
from typing import Any

from app.services.llm_service import get_llm_response_async


MEMORY_COMPARISON_PROMPT = """
You compare two candidate long-term memories for the same user.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Classify the relationship between the memories as exactly one of:
- duplicate
- compatible
- conflict
- unrelated

Definitions:
- duplicate: both memories express essentially the same underlying lasting information, even if phrased differently
- compatible: both can be true together, but they add meaningfully different information
- conflict: they appear to disagree in a meaningful way
- unrelated: they are about different things

Return this exact JSON shape:
{
  "relationship": "duplicate",
  "confidence": 0.9,
  "reason": "short explanation"
}

Rules:
- Prefer conservative decisions for conflict.
- Be more willing to use "duplicate" when two memories are clear paraphrases of the same lasting preference, fact, goal, or decision.
- Differences in wording, tone, or phrasing do NOT make memories different if the underlying meaning is the same.
- If one memory is a broader paraphrase of the other but they point to the same lasting user preference or fact, return "duplicate".
- Use "compatible" only when both memories are truly distinct and should both be preserved.
- Use "conflict" only when there is meaningful disagreement.
- If uncertain, prefer "compatible" over "conflict".

Examples:

Example 1
Existing: The user likes Taylor Swift.
New: The user is interested in Taylor Swift.
Output:
{
  "relationship": "duplicate",
  "confidence": 0.88,
  "reason": "Both express the same enduring interest in Taylor Swift."
}

Example 2
Existing: The user prefers concise answers.
New: The user likes short answers.
Output:
{
  "relationship": "duplicate",
  "confidence": 0.92,
  "reason": "Both describe the same preference for brief responses."
}

Example 3
Existing: The user prefers concise answers.
New: The user likes long, detailed answers.
Output:
{
  "relationship": "conflict",
  "confidence": 0.9,
  "reason": "The preferences point in opposite directions."
}

Example 4
Existing: The user is building a chatbot with pgvector.
New: The user is working on memory retrieval for the chatbot.
Output:
{
  "relationship": "compatible",
  "confidence": 0.86,
  "reason": "These are related but distinct facts about the user's ongoing project."
}

Example 5
Existing: The user likes Taylor Swift.
New: The user prefers concise answers.
Output:
{
  "relationship": "unrelated",
  "confidence": 0.97,
  "reason": "These memories describe different aspects of the user."
}

Do not invent facts.
"""


async def compare_memories(
    existing_content: str,
    new_content: str,
    memory_type: str,
) -> dict[str, Any]:
    prompt = f"""
{MEMORY_COMPARISON_PROMPT}

Memory type: {memory_type}

Existing memory:
{existing_content}

New memory:
{new_content}
"""

    response = await get_llm_response_async([
        {"role": "user", "content": prompt}
    ])

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return {
            "relationship": "compatible",
            "confidence": 0.5,
            "reason": "Could not parse comparator output.",
        }

    relationship = str(parsed.get("relationship", "compatible")).strip().lower()
    confidence = parsed.get("confidence", 0.5)
    reason = str(parsed.get("reason", "")).strip()

    allowed_relationships = {"duplicate", "compatible", "conflict", "unrelated"}
    if relationship not in allowed_relationships:
        relationship = "compatible"

    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5

    confidence = max(0.0, min(1.0, confidence))

    return {
        "relationship": relationship,
        "confidence": confidence,
        "reason": reason,
    }
