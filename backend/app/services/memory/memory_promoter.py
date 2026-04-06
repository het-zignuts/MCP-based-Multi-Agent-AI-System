from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message
from app.services.memory.memory_extractor import extract_memories_from_text
from app.services.memory.ltm_service import create_memory_with_embedding


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


def should_promote_memory(
    *,
    content: str,
    memory_type: str,
    importance_score: float,
    confidence_score: float,
    evidence: str,
    temporal_scope: str,
) -> bool:
    normalized = content.strip().lower()
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

    return True


async def promote_memories_from_messages(
    db: AsyncSession,
    *,
    user_id: UUID,
    messages: list[Message],
    conversation_id: UUID | None = None,
    source: str = "conversation",
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
