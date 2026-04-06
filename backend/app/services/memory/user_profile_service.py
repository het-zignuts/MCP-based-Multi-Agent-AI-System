from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.memory import get_memories_by_user
from app.services.memory.memory_comparator import compare_memories


MAX_PROFILE_ITEMS_PER_SECTION = 5
MIN_PROFILE_CONFIDENCE = 0.65
MIN_PROFILE_IMPORTANCE = 0.45
MIN_PROFILE_COMPARISON_CONFIDENCE = 0.70


@dataclass
class UserProfile:
    preferences: list[str]
    facts: list[str]
    active_goals: list[str]
    decisions: list[str]

    def to_text(self) -> str:
        sections = []

        if self.preferences:
            sections.append(
                "User preferences:\n" + "\n".join(f"- {item}" for item in self.preferences)
            )

        if self.facts:
            sections.append(
                "Known user facts:\n" + "\n".join(f"- {item}" for item in self.facts)
            )

        if self.active_goals:
            sections.append(
                "Active user goals:\n" + "\n".join(f"- {item}" for item in self.active_goals)
            )

        if self.decisions:
            sections.append(
                "Important user decisions:\n" + "\n".join(f"- {item}" for item in self.decisions)
            )

        return "\n\n".join(sections)


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _memory_confidence(memory) -> float:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    raw = metadata.get("confidence_score", 0.5)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


def _memory_importance(memory) -> float:
    try:
        return float(getattr(memory, "importance_score", 0.5) or 0.5)
    except (TypeError, ValueError):
        return 0.5


def _memory_temporal_scope(memory) -> str:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return str(metadata.get("temporal_scope", "temporary")).strip().lower()


def _memory_has_conflict(memory) -> bool:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return bool(metadata.get("conflict_detected"))


def _memory_strength(memory) -> float:
    return (0.6 * _memory_confidence(memory)) + (0.4 * _memory_importance(memory))


def _should_include_in_profile(memory) -> bool:
    content = (getattr(memory, "content", "") or "").strip()
    if not content:
        return False

    if _memory_has_conflict(memory):
        return False

    if _memory_confidence(memory) < MIN_PROFILE_CONFIDENCE:
        return False

    if _memory_importance(memory) < MIN_PROFILE_IMPORTANCE:
        return False

    memory_type = getattr(memory, "memory_type", "")
    temporal_scope = _memory_temporal_scope(memory)

    if memory_type == "preference" and temporal_scope != "durable":
        return False
    if memory_type == "fact" and temporal_scope not in {"durable", "ongoing"}:
        return False
    if memory_type == "decision" and temporal_scope not in {"durable", "ongoing"}:
        return False
    if memory_type == "task" and temporal_scope != "ongoing":
        return False

    return True


async def _consolidate_memories(memories: list, memory_type: str) -> list:
    selected = []

    for memory in memories:
        should_add = True
        replacement_index = None

        for index, existing in enumerate(selected):
            comparison = await compare_memories(
                existing_content=existing.content,
                new_content=memory.content,
                memory_type=memory_type,
            )

            relationship = comparison.get("relationship")
            confidence = float(comparison.get("confidence", 0.5) or 0.5)

            if confidence < MIN_PROFILE_COMPARISON_CONFIDENCE:
                continue

            if relationship == "duplicate":
                should_add = False
                if _memory_strength(memory) > _memory_strength(existing):
                    replacement_index = index
                break

            if relationship == "conflict":
                # Prefer the stronger one for profile display and suppress the weaker one.
                should_add = False
                if _memory_strength(memory) > _memory_strength(existing):
                    replacement_index = index
                break

        if replacement_index is not None:
            selected[replacement_index] = memory
        elif should_add:
            selected.append(memory)

    selected.sort(key=_memory_strength, reverse=True)
    return selected[:MAX_PROFILE_ITEMS_PER_SECTION]


async def build_user_profile(
    db: AsyncSession,
    *,
    user_id,
) -> UserProfile:
    memories = await get_memories_by_user(
        db,
        user_id=user_id,
        only_active=True,
    )

    filtered_memories = [
        memory
        for memory in memories
        if _should_include_in_profile(memory)
    ]

    preference_memories = [m for m in filtered_memories if m.memory_type == "preference"]
    fact_memories = [m for m in filtered_memories if m.memory_type == "fact"]
    task_memories = [m for m in filtered_memories if m.memory_type == "task"]
    decision_memories = [m for m in filtered_memories if m.memory_type == "decision"]

    preference_memories = await _consolidate_memories(preference_memories, "preference")
    fact_memories = await _consolidate_memories(fact_memories, "fact")
    task_memories = await _consolidate_memories(task_memories, "task")
    decision_memories = await _consolidate_memories(decision_memories, "decision")

    return UserProfile(
        preferences=[m.content.strip() for m in preference_memories if m.content.strip()],
        facts=[m.content.strip() for m in fact_memories if m.content.strip()],
        active_goals=[m.content.strip() for m in task_memories if m.content.strip()],
        decisions=[m.content.strip() for m in decision_memories if m.content.strip()],
    )