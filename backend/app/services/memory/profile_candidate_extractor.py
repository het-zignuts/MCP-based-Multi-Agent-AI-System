import json
from typing import Any

from app.db.models.message import Message
from app.services.llm_service import get_llm_response_async


PROFILE_CANDIDATE_PROMPT = """
You extract profile-worthy user information from conversation messages.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Extract only concrete user information that is reliable enough to keep in a long-lived user profile.
Focus on explicit durable facts, durable preferences, ongoing responsibilities, and important user decisions.
Use only user-authored evidence. Do not turn assistant guesses into profile facts.

Return this exact JSON shape:
{
  "candidates": [
    {
      "category": "identity",
      "label": "profession",
      "value": "Computer Engineer",
      "summary": "The user is a Computer Engineer by profession.",
      "section": "facts",
      "confidence": 0.97,
      "should_write_profile": true,
      "write_confidence": 0.97,
      "source_kind": "statement",
      "value_specificity": "concrete",
      "overwrite_risk": "low",
      "evidence_type": "explicit",
      "temporal_scope": "durable",
      "evidence_text": "Hey I am a Computer Engineer by profession.",
      "tags": ["profession", "work"],
      "redundancy_key": "identity:profession",
      "metadata": {
        "support_span_count": 1,
        "has_concrete_anchor": true
      }
    }
  ]
}

Rules:
- Include a candidate only when it is suitable for a user profile, not just generic long-term memory.
- Prefer explicit durable facts over inferred summaries.
- Questions, requests for recall, hypotheticals, and assistant-authored claims must NOT become profile writes.
- Use "facts" for durable personal facts, "preferences" for durable likes/dislikes, "active_goals" for ongoing responsibilities/projects, and "decisions" for durable user decisions.
- Use "durable" or "ongoing" only. Do not emit temporary items.
- `should_write_profile` must be true only when the latest user turn itself provides trustworthy evidence that should update the profile.
- `write_confidence` should reflect confidence in the write decision, not just the fact wording.
- `source_kind` must be one of: "statement", "question", "request", "correction", "assistant_claim", "hypothetical", "unclear".
- `value_specificity` must be "concrete" when the value is specific enough to be useful later, otherwise "vague".
- `overwrite_risk` must be one of: "none", "low", "high". Use "high" when the candidate is vague, weak, or likely to overwrite a stronger stored fact incorrectly.
- `label` should be short and semantic, not a sentence.
- `value` should contain the core fact value.
- `summary` should be a concise standalone sentence suitable for a profile.
- `redundancy_key` should be stable across future mentions only when the attribute should usually have one active value at a time. Leave it empty when multiple active values can coexist.
- `tags` should be a short list of useful attribute words.
- `metadata` should stay small and JSON-safe.
- If `should_write_profile` is false, you may still return the candidate for auditability, but set `write_confidence` appropriately low unless you are very sure it must not write.
- If confidence is below 0.75, do not include the candidate.
- If nothing qualifies, return {"candidates": []}.
- Do not invent facts.
"""

ALLOWED_SECTIONS = {"preferences", "facts", "active_goals", "decisions"}
ALLOWED_EVIDENCE_TYPES = {"explicit", "repeated", "inferred"}
ALLOWED_TEMPORAL_SCOPES = {"durable", "ongoing"}
ALLOWED_SOURCE_KINDS = {
    "statement",
    "question",
    "request",
    "correction",
    "assistant_claim",
    "hypothetical",
    "unclear",
}
ALLOWED_VALUE_SPECIFICITY = {"concrete", "vague"}
ALLOWED_OVERWRITE_RISK = {"none", "low", "high"}


def _message_to_line(message: Message) -> str:
    role = getattr(message, "role", "user")
    content = (getattr(message, "content", "") or "").strip()
    return f"{role}: {content}"


def _recent_history_excerpt(messages: list[Message], max_messages: int = 8) -> str:
    return "\n".join(
        _message_to_line(message)
        for message in messages[-max_messages:]
        if (getattr(message, "content", "") or "").strip()
    )


def _clean_candidate(raw_candidate: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_candidate, dict):
        return None

    label = str(raw_candidate.get("label", "") or "").strip()
    value = str(raw_candidate.get("value", "") or "").strip()
    summary = str(raw_candidate.get("summary", "") or "").strip()
    category = str(raw_candidate.get("category", "other") or "other").strip().lower()
    section = str(raw_candidate.get("section", "facts") or "facts").strip()
    should_write_profile = bool(raw_candidate.get("should_write_profile", False))
    source_kind = str(raw_candidate.get("source_kind", "unclear") or "unclear").strip().lower()
    value_specificity = str(raw_candidate.get("value_specificity", "vague") or "vague").strip().lower()
    overwrite_risk = str(raw_candidate.get("overwrite_risk", "high") or "high").strip().lower()
    evidence_type = str(raw_candidate.get("evidence_type", "inferred") or "inferred").strip().lower()
    temporal_scope = str(raw_candidate.get("temporal_scope", "durable") or "durable").strip().lower()
    evidence_text = str(raw_candidate.get("evidence_text", "") or "").strip()
    redundancy_key = str(raw_candidate.get("redundancy_key", "") or "").strip()
    metadata = raw_candidate.get("metadata", {})

    if not label or not value or not summary:
        return None
    if section not in ALLOWED_SECTIONS:
        section = "facts"
    if evidence_type not in ALLOWED_EVIDENCE_TYPES:
        evidence_type = "inferred"
    if temporal_scope not in ALLOWED_TEMPORAL_SCOPES:
        return None
    if source_kind not in ALLOWED_SOURCE_KINDS:
        source_kind = "unclear"
    if value_specificity not in ALLOWED_VALUE_SPECIFICITY:
        value_specificity = "vague"
    if overwrite_risk not in ALLOWED_OVERWRITE_RISK:
        overwrite_risk = "high"
    if not isinstance(metadata, dict):
        metadata = {}

    try:
        confidence = float(raw_candidate.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None

    try:
        write_confidence = float(raw_candidate.get("write_confidence", confidence) or confidence)
    except (TypeError, ValueError):
        write_confidence = confidence

    confidence = max(0.0, min(1.0, confidence))
    write_confidence = max(0.0, min(1.0, write_confidence))
    if confidence < 0.75:
        return None
    if not should_write_profile:
        return None
    if write_confidence < 0.80:
        return None
    if source_kind not in {"statement", "correction"}:
        return None
    if redundancy_key and value_specificity != "concrete":
        return None
    if overwrite_risk == "high":
        return None

    tags = raw_candidate.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return {
        "category": category,
        "label": label,
        "value": value,
        "summary": summary,
        "section": section,
        "confidence": confidence,
        "should_write_profile": should_write_profile,
        "write_confidence": write_confidence,
        "source_kind": source_kind,
        "value_specificity": value_specificity,
        "overwrite_risk": overwrite_risk,
        "evidence_type": evidence_type,
        "temporal_scope": temporal_scope,
        "evidence_text": evidence_text or value,
        "tags": [
            str(tag).strip().lower()
            for tag in tags
            if str(tag).strip()
        ][:8],
        "redundancy_key": redundancy_key,
        "metadata": {
            **metadata,
            "should_write_profile": should_write_profile,
            "write_confidence": write_confidence,
            "source_kind": source_kind,
            "value_specificity": value_specificity,
            "overwrite_risk": overwrite_risk,
        },
    }


async def extract_profile_candidates_from_messages(
    *,
    latest_user_message: Message,
    recent_messages: list[Message],
) -> list[dict[str, Any]]:
    latest_user_content = (getattr(latest_user_message, "content", "") or "").strip()
    if not latest_user_content:
        return []

    prompt = f"""
{PROFILE_CANDIDATE_PROMPT}

Latest user message:
\"\"\"
{latest_user_content}
\"\"\"

Recent conversation excerpt:
\"\"\"
{_recent_history_excerpt(recent_messages)}
\"\"\"
"""

    response = await get_llm_response_async(
        [{"role": "user", "content": prompt}],
        purpose="profile_extraction",
    )

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return []

    candidates = parsed.get("candidates", [])
    if not isinstance(candidates, list):
        return []

    cleaned_candidates = []
    for raw_candidate in candidates:
        cleaned = _clean_candidate(raw_candidate)
        if cleaned is None:
            continue

        cleaned["source_message_id"] = getattr(latest_user_message, "id", None)
        cleaned["source_conversation_id"] = getattr(latest_user_message, "conversation_id", None)
        cleaned_candidates.append(cleaned)

    return cleaned_candidates
