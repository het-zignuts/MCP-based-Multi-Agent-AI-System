import asyncio
from collections import defaultdict
from typing import Iterable
from uuid import UUID

from loguru import logger

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.crud.conversation import get_conversation, update_conversation_metadata
from app.services.memory.ltm_service import ComparisonBudget
from app.services.memory.memory_promoter import (
    promote_memories_from_messages,
    messages_to_conversation_text,
)
from app.services.memory.lifecycle_service import maintain_memory_lifecycle
from  app.services.conversation.conversation_metadata_extractor import extract_conversation_metadata
from  app.services.conversation.conversation_summary_memory_service import (
    promote_conversation_summary_to_ltm,
)
from app.services.user_profile.user_profile_cache_service import schedule_user_profile_refresh_if_needed
from  app.services.time.timing import elapsed_minutes, log_async_timing
from time import perf_counter
from  app.services.conversation.conversation_metadata_service import merge_conversation_metadata

_USER_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_USER_TASKS: dict[str, asyncio.Task] = {}
_USER_PENDING_CONVERSATIONS: dict[str, list[UUID]] = defaultdict(list)


def _memory_types(items: Iterable[dict]) -> set[str]:
    return {
        str(item.get("memory_type", "")).strip()
        for item in items
        if item.get("memory_type")
    }


def _has_remaining_budget(
    comparison_budget: ComparisonBudget,
    *,
    minimum_remaining: int,
) -> bool:
    remaining = comparison_budget.remaining
    return remaining is None or remaining >= minimum_remaining


async def run_memory_maintenance_pipeline(
    *,
    user_id,
    conversation_id,
) -> None:
    user_lock = _USER_LOCKS[str(user_id)]

    async with user_lock:
        async with AsyncSessionLocal() as db:
            try:
                from  app.services.conversation.history_service import fetch_conversation_history

                history_fetch_started_at = perf_counter()
                updated_messages = await fetch_conversation_history(
                    db,
                    conversation_id,
                    limit=20,
                )
                logger.info(
                    "Chat timing | stage=fetch_updated_messages | duration_min={}",
                    elapsed_minutes(history_fetch_started_at),
                )

                comparison_budget = ComparisonBudget(
                    remaining=settings.MAINTENANCE_MAX_COMPARISONS_PER_RUN
                )

                promoted_memories = await promote_memories_from_messages(
                    db,
                    user_id=user_id,
                    messages=updated_messages,
                    conversation_id=conversation_id,
                    source="conversation",
                    comparison_budget=comparison_budget,
                )
                logger.info(
                    "Background maintenance | stage=promote_memories | created_count={} | comparisons_remaining={}",
                    len(promoted_memories),
                    comparison_budget.remaining,
                )
                schedule_user_profile_refresh_if_needed(
                    user_id=user_id,
                    promoted_memories=promoted_memories,
                )
                logger.info(
                    "Background maintenance | stage=profile_refresh_schedule | scheduled={}",
                    bool(_memory_types(promoted_memories) & {"preference", "fact", "task", "decision"}),
                )

                lifecycle_result = await maintain_memory_lifecycle(
                    db,
                    user_id=user_id,
                    candidate_memory_ids=[
                        item["id"]
                        for item in promoted_memories
                        if item.get("id")
                    ],
                )
                logger.info(
                    "Background maintenance | stage=memory_lifecycle | resolved_conflicts={} | pruned_memories={}",
                    lifecycle_result["resolved_conflicts"],
                    lifecycle_result["pruned_memories"],
                )

                if _has_remaining_budget(
                    comparison_budget,
                    minimum_remaining=settings.MAINTENANCE_MIN_COMPARISONS_FOR_OPTIONAL_STAGES,
                ):
                    conversation_text = messages_to_conversation_text(updated_messages)
                    extracted_metadata = await extract_conversation_metadata(conversation_text)

                    refreshed_conversation = await get_conversation(db, conversation_id)
                    merged_metadata = merge_conversation_metadata(
                        refreshed_conversation.convo_metadata,
                        extracted_metadata.model_dump(),
                    )
                    await update_conversation_metadata(
                        db,
                        conversation_id,
                        merged_metadata,
                    )
                    logger.info(
                        "Background maintenance | stage=conversation_metadata | topics={} | entities={} | goals={}",
                        len(merged_metadata.get("topics", [])),
                        len(merged_metadata.get("entities", [])),
                        len(merged_metadata.get("active_goals", [])),
                    )

                    summary_memory = await promote_conversation_summary_to_ltm(
                        db,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        comparison_budget=comparison_budget,
                    )
                    logger.info(
                        "Background maintenance | stage=conversation_summary_promotion | created={} | comparisons_remaining={}",
                        bool(summary_memory),
                        comparison_budget.remaining,
                    )
                else:
                    logger.info(
                        "Background maintenance | stage=optional_stages | skipped=True | comparisons_remaining={}",
                        comparison_budget.remaining,
                    )

                logger.info(
                    "Background maintenance | stage=refresh_user_profile_cache | refreshed={}",
                    bool(_memory_types(promoted_memories) & {"preference", "fact", "task", "decision"}),
                )

            except Exception:
                logger.exception(
                    "Background memory maintenance failed | user_id={} | conversation_id={}",
                    user_id,
                    conversation_id,
                )


async def _run_pending_memory_maintenance_for_user(*, user_id) -> None:
    user_key = str(user_id)

    try:
        while True:
            pending_conversations = _USER_PENDING_CONVERSATIONS.get(user_key, [])
            if not pending_conversations:
                break
            conversation_id = pending_conversations.pop(0)

            await run_memory_maintenance_pipeline(
                user_id=user_id,
                conversation_id=conversation_id,
            )
    finally:
        _USER_TASKS.pop(user_key, None)
        if _USER_PENDING_CONVERSATIONS.get(user_key) and user_key not in _USER_TASKS:
            _USER_TASKS[user_key] = asyncio.create_task(
                _run_pending_memory_maintenance_for_user(user_id=user_id)
            )


def schedule_memory_maintenance_pipeline(
    *,
    user_id,
    conversation_id,
) -> None:
    user_key = str(user_id)
    pending_conversations = _USER_PENDING_CONVERSATIONS[user_key]
    if conversation_id not in pending_conversations:
        pending_conversations.append(conversation_id)

    existing_task = _USER_TASKS.get(user_key)
    if existing_task is not None and not existing_task.done():
        logger.info(
            "Background maintenance | stage=schedule | action=queued | user_id={} | conversation_id={} | pending_count={}",
            user_id,
            conversation_id,
            len(pending_conversations),
        )
        return

    logger.info(
        "Background maintenance | stage=schedule | action=started | user_id={} | conversation_id={} | pending_count={}",
        user_id,
        conversation_id,
        len(pending_conversations),
    )
    _USER_TASKS[user_key] = asyncio.create_task(
        _run_pending_memory_maintenance_for_user(user_id=user_id)
    )
