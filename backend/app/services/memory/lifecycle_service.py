from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.memory import deactivate_memory, get_memories_by_user, get_memory, update_memory
from app.schemas.memory import MemoryUpdate


WEAK_MEMORY_MIN_IMPORTANCE = 0.45
WEAK_MEMORY_MIN_CONFIDENCE = 0.60
WEAK_MEMORY_MAX_AGE_DAYS = 14
STALE_ONGOING_MAX_AGE_DAYS = 45
STALE_ONGOING_MIN_IMPORTANCE = 0.55
CONFLICT_RESOLUTION_MIN_CONFIDENCE = 0.80


def _memory_confidence(memory) -> float:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    raw = metadata.get("confidence_score", 0.5)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


def _memory_temporal_scope(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return str(metadata.get("temporal_scope", "")).strip().lower()


def _memory_strength(memory) -> float:
    importance = float(getattr(memory, "importance_score", 0.5) or 0.5)
    confidence = _memory_confidence(memory)
    return (0.6 * confidence) + (0.4 * importance)


def _memory_age_days(memory) -> float:
    updated_at = getattr(memory, "updated_at", None) or getattr(memory, "created_at", None)
    if updated_at is None:
        return 0.0
    return max((datetime.utcnow() - updated_at).total_seconds(), 0.0) / 86400.0


async def _mark_memory_lifecycle(
    db: AsyncSession,
    *,
    memory_id: UUID,
    lifecycle_state: str,
    lifecycle_reason: str,
) -> None:
    memory = await get_memory(db, memory_id)
    metadata = {
        **(memory.memory_metadata or {}),
        "lifecycle_state": lifecycle_state,
        "lifecycle_reason": lifecycle_reason,
        "lifecycle_updated_at": datetime.utcnow().isoformat(),
    }
    await update_memory(
        db,
        memory_id,
        MemoryUpdate(memory_metadata=metadata),
    )


async def _resolve_conflict_pair(
    db: AsyncSession,
    *,
    candidate_memory,
) -> bool:
    metadata = candidate_memory.memory_metadata or {}
    conflict_memory_id = metadata.get("possible_conflict_with")
    if not conflict_memory_id:
        return False

    if _memory_confidence(candidate_memory) < CONFLICT_RESOLUTION_MIN_CONFIDENCE:
        return False

    try:
        existing_memory = await get_memory(db, UUID(str(conflict_memory_id)))
    except Exception:
        return False

    if not getattr(existing_memory, "is_active", True):
        return False

    winner = candidate_memory
    loser = existing_memory
    if _memory_strength(existing_memory) > _memory_strength(candidate_memory):
        winner = existing_memory
        loser = candidate_memory

    await _mark_memory_lifecycle(
        db,
        memory_id=winner.id,
        lifecycle_state="active",
        lifecycle_reason=f"conflict_winner:{loser.id}",
    )
    await _mark_memory_lifecycle(
        db,
        memory_id=loser.id,
        lifecycle_state="superseded",
        lifecycle_reason=f"conflict_loser:{winner.id}",
    )
    await deactivate_memory(db, loser.id)
    return True


async def _prune_stale_or_weak_memories(
    db: AsyncSession,
    *,
    user_id: UUID,
) -> int:
    memories = await get_memories_by_user(
        db,
        user_id=user_id,
        only_active=True,
    )

    deactivated_count = 0
    for memory in memories:
        age_days = _memory_age_days(memory)
        confidence = _memory_confidence(memory)
        importance = float(getattr(memory, "importance_score", 0.5) or 0.5)
        temporal_scope = _memory_temporal_scope(memory)

        should_deactivate = False
        reason = ""

        if (
            age_days >= WEAK_MEMORY_MAX_AGE_DAYS
            and importance < WEAK_MEMORY_MIN_IMPORTANCE
            and confidence < WEAK_MEMORY_MIN_CONFIDENCE
        ):
            should_deactivate = True
            reason = "weak_and_stale"
        elif (
            temporal_scope == "ongoing"
            and age_days >= STALE_ONGOING_MAX_AGE_DAYS
            and importance < STALE_ONGOING_MIN_IMPORTANCE
        ):
            should_deactivate = True
            reason = "stale_ongoing"

        if not should_deactivate:
            continue

        await _mark_memory_lifecycle(
            db,
            memory_id=memory.id,
            lifecycle_state="inactive",
            lifecycle_reason=reason,
        )
        await deactivate_memory(db, memory.id)
        deactivated_count += 1

    return deactivated_count


async def maintain_memory_lifecycle(
    db: AsyncSession,
    *,
    user_id: UUID,
    candidate_memory_ids: list[UUID] | None = None,
) -> dict[str, int]:
    resolved_conflicts = 0

    for memory_id in candidate_memory_ids or []:
        memory = await get_memory(db, memory_id)
        if await _resolve_conflict_pair(
            db,
            candidate_memory=memory,
        ):
            resolved_conflicts += 1

    pruned_memories = await _prune_stale_or_weak_memories(
        db,
        user_id=user_id,
    )

    return {
        "resolved_conflicts": resolved_conflicts,
        "pruned_memories": pruned_memories,
    }
