from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.memory import get_memories_by_user
from app.crud.user_profile_snapshot import get_user_profile_snapshot
from app.services.user_profile.profile_renderer import RenderedUserProfile, render_profile_snapshot
from app.services.user_profile.profile_resolver import resolve_profile_items


PROFILE_RELEVANT_TYPES = {"preference", "fact", "task", "decision"}
MIN_PROFILE_MEMORY_CONFIDENCE = 0.75
MIN_PROFILE_MEMORY_IMPORTANCE = 0.45


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _memory_confidence(memory) -> float:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return _as_float(metadata.get("confidence_score"), 0.5)


def _memory_importance(memory) -> float:
    return _as_float(getattr(memory, "importance_score", 0.5), 0.5)


def _memory_temporal_scope(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return str(metadata.get("temporal_scope", "temporary")).strip().lower()


def _memory_has_conflict(memory) -> bool:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return bool(metadata.get("conflict_detected"))


def _memory_profile_category(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return str(metadata.get("profile_category", "other")).strip().lower()


def _memory_profile_attributes(memory) -> list[str]:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    profile_attributes = metadata.get("profile_attributes", [])
    if not isinstance(profile_attributes, list):
        return []
    return [
        str(attribute).strip().lower()
        for attribute in profile_attributes
        if str(attribute).strip()
    ][:5]


def _memory_specificity(memory) -> float:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return _as_float(metadata.get("specificity_score"), 0.5)


def _memory_has_concrete_anchor(memory) -> bool:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return bool(metadata.get("has_concrete_anchor", False))


def _memory_source_kind(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return str(metadata.get("source_kind", "statement")).strip().lower()


def _memory_profile_write_eligible(memory) -> bool:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    if "profile_write_eligible" in metadata:
        return bool(metadata.get("profile_write_eligible"))

    evidence = str(metadata.get("evidence", "explicit")).strip().lower()
    return (
        evidence in {"explicit", "repeated"}
        and _memory_has_concrete_anchor(memory)
        and _memory_specificity(memory) >= 0.75
    )


def _memory_profile_write_confidence(memory) -> float:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return _as_float(metadata.get("profile_write_confidence"), _memory_confidence(memory))


def _memory_value_specificity(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    value_specificity = str(metadata.get("value_specificity", "")).strip().lower()
    if value_specificity in {"concrete", "vague"}:
        return value_specificity
    return "concrete" if _memory_has_concrete_anchor(memory) and _memory_specificity(memory) >= 0.75 else "vague"


def _memory_overwrite_risk(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    overwrite_risk = str(metadata.get("overwrite_risk", "")).strip().lower()
    if overwrite_risk in {"none", "low", "high"}:
        return overwrite_risk
    if _memory_source_kind(memory) not in {"statement", "correction"}:
        return "high"
    if _memory_value_specificity(memory) != "concrete":
        return "high"
    return "low"


def _should_include_memory(memory) -> bool:
    if getattr(memory, "memory_type", None) not in PROFILE_RELEVANT_TYPES:
        return False
    if _memory_has_conflict(memory):
        return False
    if _memory_confidence(memory) < MIN_PROFILE_MEMORY_CONFIDENCE:
        return False
    if _memory_importance(memory) < MIN_PROFILE_MEMORY_IMPORTANCE:
        return False

    temporal_scope = _memory_temporal_scope(memory)
    memory_type = getattr(memory, "memory_type", "")

    if memory_type == "preference":
        return temporal_scope == "durable"
    if memory_type == "task":
        return temporal_scope == "ongoing"
    return temporal_scope in {"durable", "ongoing"}


def _memory_section(memory_type: str) -> str:
    mapping = {
        "preference": "preferences",
        "fact": "facts",
        "task": "active_goals",
        "decision": "decisions",
    }
    return mapping.get(memory_type, "facts")


def _memory_to_profile_candidate(memory) -> dict | None:
    if not _should_include_memory(memory):
        return None

    content = str(getattr(memory, "content", "") or "").strip()
    if not content:
        return None

    memory_type = str(getattr(memory, "memory_type", "") or "").strip().lower()
    profile_category = _memory_profile_category(memory)
    profile_attributes = _memory_profile_attributes(memory)
    evidence_type = str(
        (getattr(memory, "memory_metadata", {}) or {}).get("evidence", "explicit")
    ).strip().lower()

    label = profile_attributes[0] if profile_attributes else profile_category
    if not label or label == "other":
        label = memory_type

    redundancy_key = ""
    if profile_attributes:
        redundancy_key = f"{profile_category}:{profile_attributes[0]}"

    return {
        "category": profile_category or "other",
        "label": label,
        "value": content,
        "summary": content,
        "section": _memory_section(memory_type),
        "confidence": max(_memory_confidence(memory), _memory_importance(memory)),
        "should_write_profile": _memory_profile_write_eligible(memory),
        "write_confidence": _memory_profile_write_confidence(memory),
        "source_kind": _memory_source_kind(memory),
        "value_specificity": _memory_value_specificity(memory),
        "overwrite_risk": _memory_overwrite_risk(memory),
        "evidence_type": evidence_type if evidence_type in {"explicit", "repeated", "inferred"} else "explicit",
        "temporal_scope": _memory_temporal_scope(memory) if _memory_temporal_scope(memory) in {"durable", "ongoing"} else "durable",
        "evidence_text": content,
        "tags": profile_attributes,
        "redundancy_key": redundancy_key,
        "source_conversation_id": getattr(memory, "conversation_id", None),
        "metadata": {
            "source": getattr(memory, "source", "conversation"),
            "memory_id": str(getattr(memory, "id", "")),
            "memory_type": memory_type,
            "profile_write_eligible": _memory_profile_write_eligible(memory),
            "profile_write_confidence": _memory_profile_write_confidence(memory),
            "source_kind": _memory_source_kind(memory),
            "value_specificity": _memory_value_specificity(memory),
            "overwrite_risk": _memory_overwrite_risk(memory),
        },
    }


def merge_profile_items_from_memories(
    existing_profile_items: list[dict] | None,
    memories: list,
) -> list[dict]:
    memory_candidates = [
        candidate
        for candidate in (_memory_to_profile_candidate(memory) for memory in memories)
        if candidate is not None
    ]
    return resolve_profile_items(existing_profile_items, memory_candidates)


async def build_user_profile(
    db: AsyncSession,
    *,
    user_id,
) -> RenderedUserProfile:
    snapshot = await get_user_profile_snapshot(db, user_id=user_id)
    existing_profile_items = list(getattr(snapshot, "profile_items", []) or [])
    if existing_profile_items:
        return render_profile_snapshot(existing_profile_items)

    memories = await get_memories_by_user(
        db,
        user_id=user_id,
        only_active=True,
    )
    merged_profile_items = merge_profile_items_from_memories(existing_profile_items, memories)
    return render_profile_snapshot(merged_profile_items)
