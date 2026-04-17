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

Return this exact JSON shape:
{
  "relationship": "duplicate",
  "confidence": 0.9,
  "reason": "short explanation"
}

Rules:
- duplicate: same underlying lasting information, even if phrased differently
- compatible: both can be true and are meaningfully different
- conflict: meaningful disagreement
- unrelated: different topic
- Prefer conservative conflict detection.
- If uncertain between conflict and compatible, choose compatible.
- If wording differs but meaning is the same, choose duplicate.
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
    ], purpose=f"memory_comparison:{memory_type}")

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
