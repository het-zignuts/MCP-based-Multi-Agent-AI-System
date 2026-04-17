from copy import deepcopy
from datetime import datetime
from uuid import uuid4


MIN_PROFILE_CONFIDENCE = 0.75
MIN_PROFILE_WRITE_CONFIDENCE = 0.80
ALLOWED_EVIDENCE_TYPES = {"explicit", "repeated", "inferred"}
ALLOWED_TEMPORAL_SCOPES = {"durable", "ongoing"}
ALLOWED_SECTIONS = {"preferences", "facts", "active_goals", "decisions"}
ALLOWED_SOURCE_KINDS = {"statement", "correction"}
_EVIDENCE_WEIGHTS = {
    "explicit": 0.2,
    "repeated": 0.15,
    "inferred": 0.0,
}


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_key(value: str) -> str:
    normalized = _normalize_text(value)
    return "".join(char for char in normalized if char.isalnum() or char in {":", "_", "-", " "})


def _merge_tags(existing: list, new_tags: list) -> list[str]:
    merged = []
    seen = set()

    for value in (existing or []) + (new_tags or []):
        normalized = _normalize_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(str(value).strip().lower())

    return merged[:8]


def _candidate_score(candidate: dict) -> float:
    try:
        confidence = float(candidate.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    try:
        write_confidence = float(candidate.get("write_confidence", confidence) or confidence)
    except (TypeError, ValueError):
        write_confidence = confidence

    evidence_type = str(candidate.get("evidence_type", "inferred")).strip().lower()
    specificity_bonus = 0.1 if str(candidate.get("value_specificity", "vague")).strip().lower() == "concrete" else 0.0
    return confidence + (0.5 * write_confidence) + _EVIDENCE_WEIGHTS.get(evidence_type, 0.0) + specificity_bonus


def _canonical_key(candidate: dict) -> str:
    redundancy_key = _normalize_key(candidate.get("redundancy_key", ""))
    if redundancy_key:
        return redundancy_key

    category = _normalize_key(candidate.get("category", "other"))
    label = _normalize_key(candidate.get("label", "detail"))
    normalized_value = _normalize_key(candidate.get("normalized_value", candidate.get("value", "")))
    return f"{category}:{label}:{normalized_value}"


def _is_valid_candidate(candidate: dict) -> bool:
    if not isinstance(candidate, dict):
        return False

    value = str(candidate.get("value", "") or "").strip()
    summary = str(candidate.get("summary", "") or "").strip()
    label = str(candidate.get("label", "") or "").strip()
    if not value or not summary or not label:
        return False

    try:
        confidence = float(candidate.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False

    if confidence < MIN_PROFILE_CONFIDENCE:
        return False

    try:
        write_confidence = float(candidate.get("write_confidence", confidence) or confidence)
    except (TypeError, ValueError):
        return False

    if write_confidence < MIN_PROFILE_WRITE_CONFIDENCE:
        return False

    if not bool(candidate.get("should_write_profile", False)):
        return False

    evidence_type = str(candidate.get("evidence_type", "inferred")).strip().lower()
    if evidence_type not in ALLOWED_EVIDENCE_TYPES:
        return False

    source_kind = str(candidate.get("source_kind", "unclear")).strip().lower()
    if source_kind not in ALLOWED_SOURCE_KINDS:
        return False

    temporal_scope = str(candidate.get("temporal_scope", "durable")).strip().lower()
    if temporal_scope not in ALLOWED_TEMPORAL_SCOPES:
        return False

    overwrite_risk = str(candidate.get("overwrite_risk", "high")).strip().lower()
    if overwrite_risk == "high":
        return False

    redundancy_key = str(candidate.get("redundancy_key", "") or "").strip()
    value_specificity = str(candidate.get("value_specificity", "vague")).strip().lower()
    if redundancy_key and value_specificity != "concrete":
        return False

    return True


def _build_profile_item(candidate: dict, *, now: datetime) -> dict:
    section = str(candidate.get("section", "facts") or "facts").strip()
    if section not in ALLOWED_SECTIONS:
        section = "facts"

    normalized_value = _normalize_text(candidate.get("value", ""))
    canonical_key = _canonical_key(candidate)
    source_message_id = candidate.get("source_message_id")
    source_conversation_id = candidate.get("source_conversation_id")

    return {
        "id": candidate.get("id") or str(uuid4()),
        "category": str(candidate.get("category", "other") or "other").strip().lower(),
        "label": str(candidate.get("label", "") or "").strip(),
        "value": str(candidate.get("value", "") or "").strip(),
        "normalized_value": normalized_value,
        "summary": str(candidate.get("summary", "") or "").strip(),
        "section": section,
        "confidence": float(candidate.get("confidence", 0.0) or 0.0),
        "should_write_profile": bool(candidate.get("should_write_profile", False)),
        "write_confidence": float(candidate.get("write_confidence", candidate.get("confidence", 0.0)) or 0.0),
        "source_kind": str(candidate.get("source_kind", "statement") or "statement").strip().lower(),
        "value_specificity": str(candidate.get("value_specificity", "vague") or "vague").strip().lower(),
        "overwrite_risk": str(candidate.get("overwrite_risk", "low") or "low").strip().lower(),
        "evidence_type": str(candidate.get("evidence_type", "inferred") or "inferred").strip().lower(),
        "evidence_text": str(candidate.get("evidence_text", "") or "").strip(),
        "temporal_scope": str(candidate.get("temporal_scope", "durable") or "durable").strip().lower(),
        "status": "active",
        "tags": _merge_tags([], candidate.get("tags", [])),
        "redundancy_key": canonical_key,
        "source_message_id": str(source_message_id) if source_message_id else None,
        "source_conversation_id": str(source_conversation_id) if source_conversation_id else None,
        "first_seen_at": now.isoformat(),
        "last_confirmed_at": now.isoformat(),
        "update_count": 1,
        "metadata": deepcopy(candidate.get("metadata", {})) if isinstance(candidate.get("metadata"), dict) else {},
    }


def _matches_same_fact(existing: dict, candidate_item: dict) -> bool:
    return (
        _normalize_key(existing.get("redundancy_key", "")) == _normalize_key(candidate_item.get("redundancy_key", ""))
        and _normalize_text(existing.get("normalized_value", existing.get("value", "")))
        == _normalize_text(candidate_item.get("normalized_value", candidate_item.get("value", "")))
    )


def _matches_same_topic(existing: dict, candidate_item: dict) -> bool:
    return _normalize_key(existing.get("redundancy_key", "")) == _normalize_key(
        candidate_item.get("redundancy_key", "")
    )


def _refresh_existing_item(existing: dict, candidate_item: dict, *, now: datetime) -> None:
    existing["confidence"] = max(
        float(existing.get("confidence", 0.0) or 0.0),
        float(candidate_item.get("confidence", 0.0) or 0.0),
    )
    existing["write_confidence"] = max(
        float(existing.get("write_confidence", existing.get("confidence", 0.0)) or 0.0),
        float(candidate_item.get("write_confidence", candidate_item.get("confidence", 0.0)) or 0.0),
    )
    existing["summary"] = candidate_item.get("summary") or existing.get("summary", "")
    existing["value"] = candidate_item.get("value") or existing.get("value", "")
    existing["normalized_value"] = candidate_item.get("normalized_value") or existing.get("normalized_value", "")
    existing["should_write_profile"] = bool(candidate_item.get("should_write_profile", True))
    existing["source_kind"] = candidate_item.get("source_kind") or existing.get("source_kind", "statement")
    existing["value_specificity"] = candidate_item.get("value_specificity") or existing.get("value_specificity", "vague")
    existing["overwrite_risk"] = candidate_item.get("overwrite_risk") or existing.get("overwrite_risk", "low")
    existing["evidence_type"] = candidate_item.get("evidence_type") or existing.get("evidence_type", "inferred")
    existing["evidence_text"] = candidate_item.get("evidence_text") or existing.get("evidence_text", "")
    existing["section"] = candidate_item.get("section") or existing.get("section", "facts")
    existing["category"] = candidate_item.get("category") or existing.get("category", "other")
    existing["tags"] = _merge_tags(existing.get("tags", []), candidate_item.get("tags", []))
    existing["last_confirmed_at"] = now.isoformat()
    existing["update_count"] = int(existing.get("update_count", 1) or 1) + 1
    if candidate_item.get("source_message_id"):
        existing["source_message_id"] = candidate_item["source_message_id"]
    if candidate_item.get("source_conversation_id"):
        existing["source_conversation_id"] = candidate_item["source_conversation_id"]


def resolve_profile_items(
    existing_items: list[dict] | None,
    candidates: list[dict] | None,
) -> list[dict]:
    now = datetime.utcnow()
    resolved_items = [
        deepcopy(item)
        for item in (existing_items or [])
        if isinstance(item, dict)
    ]

    for raw_candidate in candidates or []:
        if not _is_valid_candidate(raw_candidate):
            continue

        candidate_item = _build_profile_item(raw_candidate, now=now)

        same_fact_index = next(
            (
                index
                for index, existing in enumerate(resolved_items)
                if str(existing.get("status", "active")).strip().lower() == "active"
                and _matches_same_fact(existing, candidate_item)
            ),
            None,
        )
        if same_fact_index is not None:
            _refresh_existing_item(resolved_items[same_fact_index], candidate_item, now=now)
            continue

        conflicting_index = next(
            (
                index
                for index, existing in enumerate(resolved_items)
                if str(existing.get("status", "active")).strip().lower() == "active"
                and _matches_same_topic(existing, candidate_item)
            ),
            None,
        )

        if conflicting_index is None:
            resolved_items.append(candidate_item)
            continue

        existing_item = resolved_items[conflicting_index]
        existing_specificity = str(existing_item.get("value_specificity", "vague")).strip().lower()
        candidate_specificity = str(candidate_item.get("value_specificity", "vague")).strip().lower()
        if existing_specificity == "concrete" and candidate_specificity != "concrete":
            continue

        if _candidate_score(candidate_item) >= (_candidate_score(existing_item) + 0.05):
            existing_item["status"] = "superseded"
            existing_item["last_confirmed_at"] = now.isoformat()
            resolved_items.append(candidate_item)

    return resolved_items
