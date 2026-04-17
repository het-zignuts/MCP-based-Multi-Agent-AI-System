import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message
from app.services.memory.memory_extractor import extract_memories_from_text
from app.services.memory.ltm_service import ComparisonBudget, create_memory_with_embedding


MIN_CONFIDENCE_BY_EVIDENCE = {
    "explicit": 0.55,
    "repeated": 0.60,
    "inferred": 0.80,
}

ALLOWED_TEMPORAL_SCOPE_BY_TYPE = {
    "preference": {"durable"},
    "fact": {"durable", "ongoing"},
    "decision": {"durable", "ongoing"},
    "task": {"ongoing"},
}

GENERIC_MEMORY_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "by",
    "with",
    "about",
    "from",
    "into",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "user",
    "users",
    "assistant",
    "my",
    "your",
    "their",
    "this",
    "that",
    "those",
    "these",
    "have",
    "has",
    "had",
    "does",
    "did",
    "do",
    "wants",
    "want",
    "prefers",
    "prefer",
    "likes",
    "like",
    "works",
    "work",
}


def messages_to_conversation_text(messages: list[Message]) -> str:
    lines: list[str] = []

    for message in messages:
        role = getattr(message, "role", "unknown")
        content = getattr(message, "content", "") or ""
        content = content.strip()
        if not content:
            continue

        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def _normalize_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", (text or "").lower())
        if len(token) > 2 and token not in GENERIC_MEMORY_STOP_WORDS
    }


def _memory_has_user_support(
    *,
    messages: list[Message],
    content: str,
    evidence: str,
) -> bool:
    if evidence == "inferred":
        return True

    content_terms = _normalize_terms(content)
    if not content_terms:
        return False

    user_messages = [
        (getattr(message, "content", "") or "").strip()
        for message in messages
        if getattr(message, "role", "") == "user"
    ]
    if not user_messages:
        return False

    user_terms = _normalize_terms("\n".join(user_messages))
    overlap = content_terms & user_terms

    if len(overlap) >= min(2, len(content_terms)):
        return True

    if len(content_terms) == 1 and overlap:
        return True

    return False


def should_promote_memory(
    *,
    content: str,
    memory_type: str,
    importance_score: float,
    confidence_score: float,
    evidence: str,
    temporal_scope: str,
    memory_metadata: dict | None = None,
) -> bool:
    normalized = content.strip().lower()
    metadata = memory_metadata or {}
    if not normalized:
        return False

    required_confidence = MIN_CONFIDENCE_BY_EVIDENCE.get(evidence, 0.80)
    if confidence_score < required_confidence:
        return False

    if importance_score < 0.40:
        return False

    allowed_scopes = ALLOWED_TEMPORAL_SCOPE_BY_TYPE.get(memory_type, {"durable"})
    if temporal_scope not in allowed_scopes:
        return False

    if evidence == "inferred" and memory_type in {"preference", "fact"} and importance_score < 0.60:
        return False

    if evidence == "inferred" and memory_type in {"preference", "fact"}:
        specificity_score = float(metadata.get("specificity_score", 0.5) or 0.5)
        support_span_count = int(metadata.get("support_span_count", 0) or 0)
        is_generic_persona_claim = bool(metadata.get("is_generic_persona_claim", False))
        has_concrete_anchor = bool(metadata.get("has_concrete_anchor", False))

        if confidence_score < 0.90:
            return False
        if importance_score < 0.75:
            return False
        if specificity_score < 0.70:
            return False
        if is_generic_persona_claim and support_span_count < 2:
            return False
        if not has_concrete_anchor and support_span_count < 2:
            return False

    return True


async def promote_memories_from_messages(
    db: AsyncSession,
    *,
    user_id: UUID,
    messages: list[Message],
    conversation_id: UUID | None = None,
    source: str = "conversation",
    comparison_budget: ComparisonBudget | None = None,
) -> list[dict[str, Any]]:
    conversation_text = messages_to_conversation_text(messages)
    if not conversation_text.strip():
        return []

    extracted_memories = await extract_memories_from_text(conversation_text)
    if not extracted_memories:
        return []

    created_memories: list[dict[str, Any]] = []

    for item in extracted_memories:
        content = item.get("content", "").strip()
        memory_type = item.get("memory_type", "").strip()
        importance_score = float(item.get("importance_score", 0.5))
        confidence_score = float(item.get("confidence_score", 0.5))
        evidence = str(item.get("evidence", "inferred")).strip().lower()
        temporal_scope = str(item.get("temporal_scope", "temporary")).strip().lower()
        memory_metadata = item.get("memory_metadata", {}) or {}

        if not content or not memory_type:
            continue

        if not should_promote_memory(
            content=content,
            memory_type=memory_type,
            importance_score=importance_score,
            confidence_score=confidence_score,
            evidence=evidence,
            temporal_scope=temporal_scope,
            memory_metadata=memory_metadata,
        ):
            continue

        if not _memory_has_user_support(
            messages=messages,
            content=content,
            evidence=evidence,
        ):
            continue

        memory_metadata = {
            **memory_metadata,
            "promotion_source": source,
            "confidence_score": confidence_score,
            "evidence": evidence,
            "temporal_scope": temporal_scope,
        }

        memory = await create_memory_with_embedding(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            memory_type=memory_type,
            memory_metadata=memory_metadata,
            importance_score=importance_score,
            source=source,
            comparison_budget=comparison_budget,
        )

        if memory is None:
            continue

        created_memories.append(
            {
                "id": str(memory.id),
                "content": memory.content,
                "memory_type": memory.memory_type,
                "memory_metadata": memory.memory_metadata,
                "importance_score": memory.importance_score,
                "source": memory.source,
            }
        )

    return created_memories
