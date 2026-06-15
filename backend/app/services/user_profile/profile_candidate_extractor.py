import json
from typing import Any

from app.models.message import Message
from app.schemas import ProfileCandidateResponse, ProfileCandidate
from app.services.llm import llm
from app.prompts import PROFILE_CANDIDATE_SYSTEM_PROMPT, PROFILE_CANDIDATE_USER_PROMPT


# ALLOWED_SECTIONS = {"preferences", "facts", "active_goals", "decisions"}
# ALLOWED_EVIDENCE_TYPES = {"explicit", "repeated", "inferred"}
# ALLOWED_TEMPORAL_SCOPES = {"durable", "ongoing"}
# ALLOWED_SOURCE_KINDS = {
#     "statement",
#     "question",
#     "request",
#     "correction",
#     "assistant_claim",
#     "hypothetical",
#     "unclear",
# }
# ALLOWED_VALUE_SPECIFICITY = {"concrete", "vague"}
# ALLOWED_OVERWRITE_RISK = {"none", "low", "high"}


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


# def _clean_candidate(raw_candidate: dict[str, Any]) -> dict[str, Any] | None:
#     if not isinstance(raw_candidate, dict):
#         return None

#     label = str(raw_candidate.get("label", "") or "").strip()
#     value = str(raw_candidate.get("value", "") or "").strip()
#     summary = str(raw_candidate.get("summary", "") or "").strip()
#     category = str(raw_candidate.get("category", "other") or "other").strip().lower()
#     section = str(raw_candidate.get("section", "facts") or "facts").strip()
#     should_write_profile = bool(raw_candidate.get("should_write_profile", False))
#     source_kind = str(raw_candidate.get("source_kind", "unclear") or "unclear").strip().lower()
#     value_specificity = str(raw_candidate.get("value_specificity", "vague") or "vague").strip().lower()
#     overwrite_risk = str(raw_candidate.get("overwrite_risk", "high") or "high").strip().lower()
#     evidence_type = str(raw_candidate.get("evidence_type", "inferred") or "inferred").strip().lower()
#     temporal_scope = str(raw_candidate.get("temporal_scope", "durable") or "durable").strip().lower()
#     evidence_text = str(raw_candidate.get("evidence_text", "") or "").strip()
#     redundancy_key = str(raw_candidate.get("redundancy_key", "") or "").strip()
#     metadata = raw_candidate.get("metadata", {})

#     if not label or not value or not summary:
#         return None
#     if section not in ALLOWED_SECTIONS:
#         section = "facts"
#     if evidence_type not in ALLOWED_EVIDENCE_TYPES:
#         evidence_type = "inferred"
#     if temporal_scope not in ALLOWED_TEMPORAL_SCOPES:
#         return None
#     if source_kind not in ALLOWED_SOURCE_KINDS:
#         source_kind = "unclear"
#     if value_specificity not in ALLOWED_VALUE_SPECIFICITY:
#         value_specificity = "vague"
#     if overwrite_risk not in ALLOWED_OVERWRITE_RISK:
#         overwrite_risk = "high"
#     if not isinstance(metadata, dict):
#         metadata = {}

#     try:
#         confidence = float(raw_candidate.get("confidence", 0.0) or 0.0)
#     except (TypeError, ValueError):
#         return None

#     try:
#         write_confidence = float(raw_candidate.get("write_confidence", confidence) or confidence)
#     except (TypeError, ValueError):
#         write_confidence = confidence

#     confidence = max(0.0, min(1.0, confidence))
#     write_confidence = max(0.0, min(1.0, write_confidence))
#     if confidence < 0.75:
#         return None
#     if not should_write_profile:
#         return None
#     if write_confidence < 0.80:
#         return None
#     if source_kind not in {"statement", "correction"}:
#         return None
#     if redundancy_key and value_specificity != "concrete":
#         return None
#     if overwrite_risk == "high":
#         return None

#     tags = raw_candidate.get("tags", [])
#     if not isinstance(tags, list):
#         tags = []

#     return {
#         "category": category,
#         "label": label,
#         "value": value,
#         "summary": summary,
#         "section": section,
#         "confidence": confidence,
#         "should_write_profile": should_write_profile,
#         "write_confidence": write_confidence,
#         "source_kind": source_kind,
#         "value_specificity": value_specificity,
#         "overwrite_risk": overwrite_risk,
#         "evidence_type": evidence_type,
#         "temporal_scope": temporal_scope,
#         "evidence_text": evidence_text or value,
#         "tags": [
#             str(tag).strip().lower()
#             for tag in tags
#             if str(tag).strip()
#         ][:8],
#         "redundancy_key": redundancy_key,
#         "metadata": {
#             **metadata,
#             "should_write_profile": should_write_profile,
#             "write_confidence": write_confidence,
#             "source_kind": source_kind,
#             "value_specificity": value_specificity,
#             "overwrite_risk": overwrite_risk,
#         },
#     }

def _accept_candidate(
    candidate: ProfileCandidate,
) -> bool:
    if candidate.confidence < 0.75:
        return False
    if not candidate.should_write_profile:
        return False
    if candidate.write_confidence < 0.80:
        return False
    if candidate.source_kind not in {
        "statement",
        "correction",
    }:
        return False
    if (
        candidate.redundancy_key
        and candidate.value_specificity != "concrete"
    ):
        return False
    if candidate.overwrite_risk == "high":
        return False
    return True

async def extract_profile_candidates_from_messages(
    *,
    latest_user_message: Message,
    recent_messages: list[Message],
) -> list[dict[str, Any]]:
    latest_user_content = (getattr(latest_user_message, "content", "") or "").strip()
    if not latest_user_content:
        return []

    user_prompt = PROFILE_CANDIDATE_USER_PROMPT.format(
        latest_user_content=latest_user_content,
        recent_messages=_recent_history_excerpt(recent_messages),
    )
    try:
        result = await llm.structured(
            [{"role": "system", "content": PROFILE_CANDIDATE_SYSTEM_PROMPT},{"role": "user", "content": user_prompt}],
            purpose="profile_extraction",
            response_model=ProfileCandidateResponse
        )

    except Exception:
        return []
    
    cleaned_candidates = []

    for candidate in result.candidates:
        if not _accept_candidate(candidate):
            continue
        candidate_dict = candidate.model_dump()
        candidate_dict["source_message_id"] = getattr(
            latest_user_message,
            "id",
            None,
        )
        candidate_dict["source_conversation_id"] = getattr(
            latest_user_message,
            "conversation_id",
            None,
        )
        cleaned_candidates.append(candidate_dict)
    return cleaned_candidates