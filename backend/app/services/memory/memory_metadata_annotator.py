import json
from typing import Any

from app.services.llm_service import get_llm_response_async


MEMORY_METADATA_ANNOTATION_PROMPT = """
You classify an existing durable memory so it can be used in a structured user profile.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Return this exact JSON shape:
{
  "profile_category": "other",
  "profile_attributes": [],
  "confidence": 0.0
}

Rules:
- profile_category must be exactly one of:
  - identity
  - preference
  - project
  - relationship
  - wellbeing
  - other
- profile_attributes must be a short list of durable user attributes explicitly represented in the memory.
- Allowed profile_attributes examples: name, profession, role, company, location, education, age, identity, relationship, wellbeing.
- Use an empty list when no durable profile attribute is explicitly present.
- Only mark profile_category as identity when the memory clearly describes who the user is or a stable attribute of the user's identity.
- Prefer conservative labeling.
- Do not infer beyond the memory text itself.
- confidence must be a float between 0.0 and 1.0.
"""


async def annotate_memory_profile_metadata(
    *,
    content: str,
    memory_type: str,
) -> dict[str, Any]:
    prompt = f"""
{MEMORY_METADATA_ANNOTATION_PROMPT}

Memory type:
{memory_type.strip()}

Memory content:
\"\"\"
{content.strip()}
\"\"\"
"""

    try:
        response = await get_llm_response_async(
            [{"role": "user", "content": prompt}],
            purpose="memory_annotation",
        )
        parsed = json.loads(response)
    except Exception:
        return {
            "profile_category": "other",
            "profile_attributes": [],
            "confidence": 0.0,
        }

    profile_category = str(parsed.get("profile_category", "other")).strip().lower()
    allowed_categories = {
        "identity",
        "preference",
        "project",
        "relationship",
        "wellbeing",
        "other",
    }
    if profile_category not in allowed_categories:
        profile_category = "other"

    raw_attributes = parsed.get("profile_attributes", [])
    if not isinstance(raw_attributes, list):
        raw_attributes = []
    profile_attributes = [
        str(attribute).strip().lower()
        for attribute in raw_attributes
        if str(attribute).strip()
    ][:5]

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "profile_category": profile_category,
        "profile_attributes": profile_attributes,
        "confidence": confidence,
    }
