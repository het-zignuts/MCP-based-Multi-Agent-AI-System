import asyncio
import re

from loguru import logger

from app.crud.memory import get_memories_by_user
from app.crud.user_profile_snapshot import (
    get_user_profile_snapshot,
    upsert_user_profile_snapshot,
)
from app.db.database import AsyncSessionLocal
from app.db.models.message import Message
from app.services.memory.history_service import fetch_conversation_history
from app.services.memory.profile_candidate_extractor import (
    extract_profile_candidates_from_messages,
)
from app.services.memory.profile_renderer import render_profile_snapshot
from app.services.memory.profile_resolver import resolve_profile_items
from app.services.memory.user_profile_service import (
    PROFILE_RELEVANT_TYPES,
    merge_profile_items_from_memories,
)

PROFILE_QUERY_MAX_ITEMS = 4


def _normalize_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower().replace("_", " "))
        if len(token) > 1
    }


def _active_profile_items(profile_items: list[dict]) -> list[dict]:
    return [
        item
        for item in (profile_items or [])
        if isinstance(item, dict) and str(item.get("status", "active")).strip().lower() == "active"
    ]


def _profile_item_query_score(query_text: str, item: dict) -> float:
    query_terms = _normalize_terms(query_text)
    if not query_terms:
        return 0.0

    item_text = " ".join(
        part
        for part in [
            str(item.get("label", "") or ""),
            str(item.get("value", "") or ""),
            str(item.get("summary", "") or ""),
            str(item.get("category", "") or ""),
            str(item.get("section", "") or ""),
            str(item.get("redundancy_key", "") or ""),
            " ".join(str(tag) for tag in (item.get("tags") or [])),
        ]
        if part
    ).strip()
    item_terms = _normalize_terms(item_text)
    if not item_terms:
        return 0.0

    overlap = query_terms & item_terms
    if not overlap:
        return 0.0

    label_terms = _normalize_terms(str(item.get("label", "") or ""))
    tag_terms = _normalize_terms(" ".join(str(tag) for tag in (item.get("tags") or [])))
    score = float(len(overlap))
    score += 1.5 * len(overlap & label_terms)
    score += 1.0 * len(overlap & tag_terms)
    return score


def _render_relevant_profile_text(
    *,
    profile_items: list[dict],
    query_text: str,
    max_items: int = PROFILE_QUERY_MAX_ITEMS,
) -> str:
    active_items = _active_profile_items(profile_items)
    if not active_items:
        return ""

    relevant_items = [
        item
        for item, score in sorted(
            (
                (item, _profile_item_query_score(query_text, item))
                for item in active_items
            ),
            key=lambda pair: pair[1],
            reverse=True,
        )
        if score > 0.0
    ][:max_items]

    if not relevant_items:
        return ""

    return render_profile_snapshot(relevant_items).profile_text


async def get_cached_user_profile_text(
    db,
    *,
    user_id,
    query_text: str | None = None,
) -> str:
    snapshot = await get_user_profile_snapshot(db, user_id=user_id)
    if not snapshot:
        return ""

    if query_text:
        relevant_profile_text = _render_relevant_profile_text(
            profile_items=list(snapshot.profile_items or []),
            query_text=query_text,
        )
        if relevant_profile_text:
            return relevant_profile_text.strip()

    if snapshot.profile_text:
        return snapshot.profile_text.strip()

    rendered = render_profile_snapshot(list(snapshot.profile_items or []))
    if not rendered.profile_text:
        return ""

    await upsert_user_profile_snapshot(
        db,
        user_id=user_id,
        profile_text=rendered.profile_text,
        profile_items=list(snapshot.profile_items or []),
        preferences=rendered.preferences,
        facts=rendered.facts,
        active_goals=rendered.active_goals,
        decisions=rendered.decisions,
        source_memory_count=max(len(rendered.profile_items), int(snapshot.source_memory_count or 0)),
    )
    return rendered.profile_text.strip()


async def _persist_rendered_profile(
    db,
    *,
    user_id,
    profile_items: list[dict],
    source_memory_count: int,
):
    rendered = render_profile_snapshot(profile_items)
    return await upsert_user_profile_snapshot(
        db,
        user_id=user_id,
        profile_text=rendered.profile_text,
        profile_items=profile_items,
        preferences=rendered.preferences,
        facts=rendered.facts,
        active_goals=rendered.active_goals,
        decisions=rendered.decisions,
        source_memory_count=source_memory_count,
    )


async def update_profile_snapshot_from_user_message(
    db,
    *,
    user_message: Message,
    history_limit: int = 8,
):
    try:
        recent_messages = await fetch_conversation_history(
            db,
            user_message.conversation_id,
            limit=history_limit,
        )
        candidates = await extract_profile_candidates_from_messages(
            latest_user_message=user_message,
            recent_messages=recent_messages,
        )
        if not candidates:
            return None

        snapshot = await get_user_profile_snapshot(db, user_id=user_message.user_id)
        existing_items = list(getattr(snapshot, "profile_items", []) or [])
        resolved_items = resolve_profile_items(existing_items, candidates)
        if resolved_items == existing_items and snapshot is not None:
            return snapshot

        active_memories = await get_memories_by_user(
            db,
            user_id=user_message.user_id,
            only_active=True,
        )
        profile_relevant_count = sum(
            1 for memory in active_memories
            if getattr(memory, "memory_type", None) in PROFILE_RELEVANT_TYPES
        )

        return await _persist_rendered_profile(
            db,
            user_id=user_message.user_id,
            profile_items=resolved_items,
            source_memory_count=max(profile_relevant_count, len(resolved_items)),
        )
    except Exception:
        logger.exception(
            "Foreground profile snapshot update failed | user_id={} | conversation_id={} | message_id={}",
            getattr(user_message, "user_id", None),
            getattr(user_message, "conversation_id", None),
            getattr(user_message, "id", None),
        )
        return None


async def refresh_user_profile_cache(
    db,
    *,
    user_id,
):
    snapshot = await get_user_profile_snapshot(db, user_id=user_id)
    existing_items = list(getattr(snapshot, "profile_items", []) or [])
    active_memories = await get_memories_by_user(
        db,
        user_id=user_id,
        only_active=True,
    )

    merged_items = merge_profile_items_from_memories(existing_items, active_memories)

    profile_relevant_count = sum(
        1 for memory in active_memories
        if getattr(memory, "memory_type", None) in PROFILE_RELEVANT_TYPES
    )

    return await _persist_rendered_profile(
        db,
        user_id=user_id,
        profile_items=merged_items,
        source_memory_count=max(profile_relevant_count, len(merged_items)),
    )


async def refresh_user_profile_cache_with_new_session(
    *,
    user_id,
):
    async with AsyncSessionLocal() as db:
        try:
            await refresh_user_profile_cache(db, user_id=user_id)
            logger.info("Background user profile refresh complete | user_id={}", user_id)
        except Exception:
            logger.exception("Background user profile refresh failed | user_id={}", user_id)


def schedule_user_profile_refresh_if_needed(
    *,
    user_id,
    promoted_memories: list[dict],
) -> None:
    should_refresh = any(
        item.get("memory_type") in PROFILE_RELEVANT_TYPES
        for item in promoted_memories
    )

    if not should_refresh:
        return

    asyncio.create_task(
        refresh_user_profile_cache_with_new_session(user_id=user_id)
    )


def schedule_user_profile_refresh(
    *,
    user_id,
) -> None:
    asyncio.create_task(
        refresh_user_profile_cache_with_new_session(user_id=user_id)
    )
