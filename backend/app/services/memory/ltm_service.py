from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.memory import create_memory, get_recent_memories_by_type, touch_memory
from app.models import Memory
from app.schemas.memory import MemoryCreate
from app.services.embeddings.embedding_utils import embed_text_async
from app.services.memory.memory_comparator import compare_memories


DEFAULT_DEDUP_DISTANCE_THRESHOLD = 0.18
FACT_CONFLICT_COMPARISON_MAX_DISTANCE = 1.10
FACT_CONFLICT_MIN_TOKEN_OVERLAP = 1

DEDUP_DISTANCE_BY_TYPE = {
    "preference": 0.14,
    "decision": 0.16,
    "fact": 0.18,
    "task": 0.16,
    "conversation_summary": 0.20,
}

MEMORY_TYPE_PRIORITY = {
    "preference": 1.0,
    "decision": 0.95,
    "fact": 0.85,
    "task": 0.8,
    "conversation_summary": 0.88,
}


MIN_DUPLICATE_COMPARISON_CONFIDENCE = 0.70
MIN_CONFLICT_COMPARISON_CONFIDENCE = 0.70
RECENT_CONFLICT_CHECK_LIMIT = 8


@dataclass
class ComparisonBudget:
    remaining: int | None = None

    def try_consume(self) -> bool:
        if self.remaining is None:
            return True
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


def _normalize_memory_text(text: str) -> str:
    normalized = " ".join((text or "").strip().lower().split())
    return "".join(char for char in normalized if char.isalnum() or char.isspace())


def _normalize_similarity(distance: float) -> float:
    return 1.0 / (1.0 + max(distance, 0.0))


def _content_terms(text: str) -> set[str]:
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "user",
        "users",
        "name",
        "my",
        "your",
        "their",
        "this",
        "that",
        "with",
        "from",
        "into",
        "about",
        "have",
        "has",
        "had",
        "for",
        "and",
        "but",
        "not",
        "who",
        "what",
    }
    normalized = _normalize_memory_text(text)
    return {
        token for token in normalized.split()
        if len(token) > 2 and token not in stop_words
    }


def _normalize_recency(memory: Memory) -> float:
    updated_at = getattr(memory, "updated_at", None)
    if not updated_at:
        return 0.5

    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    age_seconds = max((now - updated_at).total_seconds(), 0.0)
    age_days = age_seconds / 86400.0
    return 1.0 / (1.0 + age_days)


def _memory_type_weight(memory_type: str) -> float:
    return MEMORY_TYPE_PRIORITY.get(memory_type, 0.75)


def _compute_rank_score(memory: Memory, distance: float) -> float:
    similarity_score = _normalize_similarity(distance)
    importance_score = float(getattr(memory, "importance_score", 0.5) or 0.5)
    recency_score = _normalize_recency(memory)
    type_score = _memory_type_weight(getattr(memory, "memory_type", ""))

    return (
        0.50 * similarity_score
        + 0.20 * importance_score
        + 0.20 * recency_score
        + 0.10 * type_score
    )


def _dedup_threshold_for_type(memory_type: str) -> float:
    return DEDUP_DISTANCE_BY_TYPE.get(memory_type, DEFAULT_DEDUP_DISTANCE_THRESHOLD)


def _merge_metadata(
    existing_metadata: dict | None,
    new_metadata: dict | None,
    *,
    distance: float,
    comparison: dict | None = None,
) -> dict:
    merged = {
        **(existing_metadata or {}),
        **(new_metadata or {}),
        "last_dedup_distance": distance,
        "dedup_merged": True,
    }

    if comparison:
        merged["comparison_relationship"] = comparison.get("relationship")
        merged["comparison_confidence"] = comparison.get("confidence")
        merged["comparison_reason"] = comparison.get("reason")

    return merged


async def _check_duplicate_candidates(
    *,
    content: str,
    memory_type: str,
    similar_matches: list[dict],
    comparison_budget: ComparisonBudget | None = None,
) -> tuple[Memory | None, dict | None, float | None]:
    for candidate in similar_matches:
        existing_memory = candidate["memory"]
        distance = candidate["distance"]

        if _normalize_memory_text(existing_memory.content) == _normalize_memory_text(content):
            return existing_memory, {
                "relationship": "duplicate",
                "confidence": 1.0,
                "reason": "exact normalized text match",
            }, distance

        if comparison_budget is not None and not comparison_budget.try_consume():
            logger.info(
                "Memory comparison budget exhausted | stage=dedup | memory_type={}",
                memory_type,
            )
            break

        comparison = await compare_memories(
            existing_content=existing_memory.content,
            new_content=content,
            memory_type=memory_type,
        )

        relationship = comparison.get("relationship")
        confidence = float(comparison.get("confidence", 0.5) or 0.5)

        if relationship == "duplicate" and confidence >= MIN_DUPLICATE_COMPARISON_CONFIDENCE:
            return existing_memory, comparison, distance

    return None, None, None


async def _check_conflict_candidates(
    *,
    content: str,
    memory_type: str,
    recent_memories: list[Memory],
    embedding: list[float] | None = None,
    comparison_budget: ComparisonBudget | None = None,
) -> tuple[Memory | None, dict | None]:
    new_terms = _content_terms(content)
    for existing_memory in recent_memories:
        if _normalize_memory_text(existing_memory.content) == _normalize_memory_text(content):
            return None, None

        if memory_type == "fact":
            existing_embedding = getattr(existing_memory, "embedding", None)
            distance = None
            if embedding is not None and existing_embedding is not None:
                try:
                    distance = sum(
                        (float(left) - float(right)) ** 2
                        for left, right in zip(existing_embedding, embedding)
                    ) ** 0.5
                except (TypeError, ValueError):
                    distance = None

            overlap = len(_content_terms(existing_memory.content) & new_terms)
            if distance is not None and distance > FACT_CONFLICT_COMPARISON_MAX_DISTANCE:
                if overlap < FACT_CONFLICT_MIN_TOKEN_OVERLAP:
                    continue
            elif overlap < FACT_CONFLICT_MIN_TOKEN_OVERLAP and distance is None:
                continue

        if comparison_budget is not None and not comparison_budget.try_consume():
            logger.info(
                "Memory comparison budget exhausted | stage=conflict | memory_type={}",
                memory_type,
            )
            break

        comparison = await compare_memories(
            existing_content=existing_memory.content,
            new_content=content,
            memory_type=memory_type,
        )
        comparison=comparison.model_dump()
        relationship = comparison.get("relationship")
        confidence = float(comparison.get("confidence", 0.5) or 0.5)

        if relationship == "conflict" and confidence >= MIN_CONFLICT_COMPARISON_CONFIDENCE:
            return existing_memory, comparison

    return None, None


async def create_memory_with_embedding(
    db: AsyncSession,
    *,
    user_id: UUID,
    content: str,
    memory_type: str,
    conversation_id: UUID | None = None,
    memory_metadata: dict | None = None,
    importance_score: float = 0.5,
    source: str = "conversation",
    comparison_budget: ComparisonBudget | None = None,
) -> Memory | None:
    content = content.strip()
    if not content:
        return None

    embedding = await embed_text_async(content)

    # Path A: tight semantic candidates for duplicate detection
    similar_matches = await find_similar_memory(
        db,
        user_id=user_id,
        query_embedding=embedding,
        memory_type=memory_type,
        conversation_id=None,
        top_k=5,
    )

    threshold = _dedup_threshold_for_type(memory_type)
    dedup_candidates = [
        item for item in similar_matches
        if item["distance"] <= threshold
    ]

    matched_memory, comparison, distance = await _check_duplicate_candidates(
        content=content,
        memory_type=memory_type,
        similar_matches=dedup_candidates,
        comparison_budget=comparison_budget,
    )

    if matched_memory is not None:
        merged_metadata = _merge_metadata(
            matched_memory.memory_metadata,
            memory_metadata,
            distance=distance or 0.0,
            comparison=comparison,
        )

        return await touch_memory(
            db,
            matched_memory.id,
            content=content,
            memory_metadata=merged_metadata,
            importance_score=max(matched_memory.importance_score, importance_score),
            source=source,
            embedding=embedding,
        )

    # Path B: broader recent same-type check for conflicts
    recent_same_type_memories = await get_recent_memories_by_type(
        db,
        user_id=user_id,
        memory_type=memory_type,
        limit=RECENT_CONFLICT_CHECK_LIMIT,
        only_active=True,
    )

    # Avoid re-checking exact ids already seen in dedup candidates
    dedup_candidate_ids = {
        str(item["memory"].id)
        for item in dedup_candidates
    }
    recent_same_type_memories = [
        memory
        for memory in recent_same_type_memories
        if str(memory.id) not in dedup_candidate_ids
    ]

    conflict_memory, conflict_comparison = await _check_conflict_candidates(
        content=content,
        memory_type=memory_type,
        recent_memories=recent_same_type_memories,
        embedding=embedding,
        comparison_budget=comparison_budget,
    )

    if conflict_memory is not None:
        conflict_metadata = {
            **(memory_metadata or {}),
            "possible_conflict_with": str(conflict_memory.id),
            "conflict_detected": True,
            "comparison_relationship": conflict_comparison.get("relationship"),
            "comparison_confidence": conflict_comparison.get("confidence"),
            "comparison_reason": conflict_comparison.get("reason", ""),
        }

        payload = MemoryCreate(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            memory_type=memory_type,
            memory_metadata=conflict_metadata,
            importance_score=importance_score,
            source=source,
            embedding=embedding,
        )
        return await create_memory(db, payload)

    payload = MemoryCreate(
        user_id=user_id,
        conversation_id=conversation_id,
        content=content,
        memory_type=memory_type,
        memory_metadata=memory_metadata or {},
        importance_score=importance_score,
        source=source,
        embedding=embedding,
    )
    return await create_memory(db, payload)


async def search_memories(
    db: AsyncSession,
    *,
    user_id: UUID,
    query_text: str,
    top_k: int = 5,
    memory_type: str | None = None,
    conversation_id: UUID | None = None,
    only_active: bool = True,
) -> list[Memory]:
    ranked_results = await search_memories_with_scores(
        db,
        user_id=user_id,
        query_text=query_text,
        top_k=top_k,
        memory_type=memory_type,
        conversation_id=conversation_id,
        only_active=only_active,
    )
    return [item["memory"] for item in ranked_results]


async def search_memories_with_scores(
    db: AsyncSession,
    *,
    user_id: UUID,
    query_text: str,
    top_k: int = 5,
    memory_type: str | None = None,
    conversation_id: UUID | None = None,
    only_active: bool = True,
) -> list[dict]:
    query_embedding = await embed_text_async(query_text)

    raw_results = await find_similar_memory(
        db,
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=max(top_k * 3, 10),
        memory_type=memory_type,
        conversation_id=conversation_id,
        only_active=only_active,
    )

    ranked_results = []
    for item in raw_results:
        memory = item["memory"]
        distance = item["distance"]
        rank_score = _compute_rank_score(memory, distance)
        ranked_results.append(
            {
                "memory": memory,
                "distance": distance,
                "rank_score": rank_score,
            }
        )

    ranked_results.sort(key=lambda item: item["rank_score"], reverse=True)
    return ranked_results[:top_k]


async def find_similar_memory(
    db: AsyncSession,
    *,
    user_id: UUID,
    query_embedding: list[float],
    top_k: int = 5,
    memory_type: str | None = None,
    conversation_id: UUID | None = None,
    only_active: bool = True,
) -> list[dict]:
    distance_expr = Memory.embedding.l2_distance(query_embedding)

    query = select(Memory, distance_expr.label("distance")).where(Memory.user_id == user_id)

    if only_active:
        query = query.where(Memory.is_active == True)

    if memory_type:
        query = query.where(Memory.memory_type == memory_type)

    if conversation_id:
        query = query.where(Memory.conversation_id == conversation_id)

    query = (
        query
        .where(Memory.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "memory": row[0],
            "distance": float(row[1]),
        }
        for row in rows
    ]
