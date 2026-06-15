from dataclasses import dataclass
from time import perf_counter

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.conversation import get_conversation
from app.models.message import Message
from app.services.conversation.history_service import fetch_conversation_history
from app.services.memory.context_router import (
    ContextPolicy,
    route_context_policy,
)
from app.services.memory.ltm_service import search_memories_with_scores
from app.services.user_profile.user_profile_cache_service import get_cached_user_profile_text
from app.services.memory.memory_services import build_smart_history, get_stm_state
from app.services.time.timing import elapsed_minutes, log_async_timing


@dataclass
class UnifiedMemoryContext:
    messages: list
    stm_state: dict
    stm_summary: str
    context_policy: ContextPolicy
    ltm_results: list[dict]
    related_conversation_results: list[dict]
    conversation_metadata: dict
    user_profile_text: str
    ltm_context: str
    related_conversations_context: str
    rag_context: str
    combined_context: str


def build_ltm_context(search_results: list[dict], max_items: int = 3) -> str:
    if not search_results:
        return ""

    lines = []
    for item in search_results[:max_items]:
        memory = item["memory"]
        distance = item["distance"]
        rank_score = item.get("rank_score")

        suffix = f"importance={memory.importance_score}, distance={distance:.4f}"
        if rank_score is not None:
            suffix += f", rank={rank_score:.4f}"

        lines.append(f"- [{memory.memory_type}] {memory.content} ({suffix})")

    return "Relevant long-term memory:\n" + "\n".join(lines)


def build_related_conversations_context(
    search_results: list[dict],
    *,
    current_conversation_id,
    max_items: int = 2,
) -> str:
    if not search_results:
        return ""

    lines = []
    for item in search_results:
        memory = item["memory"]
        if memory.conversation_id == current_conversation_id:
            continue

        metadata = memory.memory_metadata or {}
        summary_hint = metadata.get("summary_hint") or ""
        distance = item["distance"]
        rank_score = item.get("rank_score")

        suffix_parts = [f"distance={distance:.4f}"]
        if rank_score is not None:
            suffix_parts.append(f"rank={rank_score:.4f}")
        if summary_hint:
            suffix_parts.append(f"focus={summary_hint}")

        lines.append(
            f"- [conversation {memory.conversation_id}] {memory.content} ({', '.join(suffix_parts)})"
        )

        if len(lines) >= max_items:
            break

    if not lines:
        return ""

    return "Related past conversations:\n" + "\n".join(lines)


def build_metadata_context(conversation_metadata: dict | None) -> str:
    if not conversation_metadata:
        return ""

    topics = conversation_metadata.get("topics") or []
    entities = conversation_metadata.get("entities") or []
    active_goals = conversation_metadata.get("active_goals") or []
    sentiment = conversation_metadata.get("sentiment") or ""
    summary_hint = conversation_metadata.get("summary_hint") or ""

    lines = []

    if topics:
        lines.append("Topics: " + ", ".join(topics))
    if entities:
        lines.append("Entities: " + ", ".join(entities))
    if active_goals:
        lines.append("Active goals: " + "; ".join(active_goals))
    if sentiment:
        lines.append(f"Sentiment: {sentiment}")
    if summary_hint:
        lines.append(f"Conversation focus: {summary_hint}")

    if not lines:
        return ""

    return "Conversation metadata:\n" + "\n".join(lines)


def merge_contexts(*contexts: str) -> str:
    cleaned = [context.strip() for context in contexts if context and context.strip()]
    return "\n\n---\n\n".join(cleaned)


def _is_stm_summary_message(message: Message) -> bool:
    return (
        getattr(message, "role", "") == "system"
        and (getattr(message, "content", "") or "").startswith(
            "Compressed memory from earlier conversation."
        )
    )


def filter_messages_for_policy(
    messages: list[Message],
    policy: ContextPolicy,
    *,
    preserve_min_messages: int = 1,
) -> list[Message]:
    filtered_messages = list(messages)
    if not policy.needs_stm_summary:
        filtered_messages = [
            message
            for message in filtered_messages
            if not _is_stm_summary_message(message)
        ]

    if policy.needs_recent_history:
        return filtered_messages
    if preserve_min_messages <= 0:
        return []
    return filtered_messages[-preserve_min_messages:]


@log_async_timing("build_unified_memory_context")
async def build_unified_memory_context(
    db: AsyncSession,
    *,
    conversation_id,
    user_id,
    query_text: str,
    rag_context: str = "",
    history_limit: int = 200,
    ltm_top_k: int = 3,
):
    conversation_started_at = perf_counter()
    conversation = await get_conversation(db, conversation_id)
    logger.info(
        "Unified memory timing | stage=get_conversation | duration_min={}",
        elapsed_minutes(conversation_started_at),
    )

    history_started_at = perf_counter()
    raw_messages = await fetch_conversation_history(
        db,
        conversation_id,
        limit=history_limit,
    )
    logger.info(
        "Unified memory timing | stage=fetch_conversation_history | duration_min={}",
        elapsed_minutes(history_started_at),
    )

    routing_started_at = perf_counter()
    context_policy = await route_context_policy(
        query_text=query_text,
        recent_messages=raw_messages,
        has_rag_context=bool((rag_context or "").strip()),
    )
    logger.info(
        "Unified memory policy | recent={} | stm={} | files={} | profile={} | ltm={} | related={} | metadata={} | self_contained={} | topic_shift={} | temporary_modes={} | confidence={} | reason={}",
        context_policy.needs_recent_history,
        context_policy.needs_stm_summary,
        context_policy.needs_file_context,
        context_policy.needs_user_profile,
        context_policy.needs_long_term_memory,
        context_policy.needs_related_conversations,
        context_policy.needs_conversation_metadata,
        context_policy.is_self_contained,
        context_policy.is_topic_shift,
        context_policy.allow_temporary_modes,
        context_policy.confidence,
        context_policy.reason,
    )
    logger.info(
        "Unified memory timing | stage=route_context_policy | duration_min={}",
        elapsed_minutes(routing_started_at),
    )

    smart_history_started_at = perf_counter()
    messages, stm_state, _ = await build_smart_history(
        raw_messages,
        convo_metadata=conversation.convo_metadata,
    )
    logger.info(
        "Unified memory timing | stage=build_smart_history | duration_min={}",
        elapsed_minutes(smart_history_started_at),
    )
    messages = filter_messages_for_policy(messages, context_policy)

    ltm_search_started_at = perf_counter()
    if context_policy.needs_long_term_memory:
        all_ltm_results = await search_memories_with_scores(
            db,
            user_id=user_id,
            query_text=query_text,
            top_k=max(ltm_top_k * 2, 6),
            conversation_id=None,
            only_active=True,
        )
    else:
        all_ltm_results = []
    logger.info(
        "Unified memory timing | stage=search_ltm_memories | duration_min={}",
        elapsed_minutes(ltm_search_started_at),
    )
    ltm_results = [
        item
        for item in all_ltm_results
        if item["memory"].memory_type != "conversation_summary"
    ][:ltm_top_k]

    related_search_started_at = perf_counter()
    if context_policy.needs_related_conversations:
        related_conversation_results = await search_memories_with_scores(
            db,
            user_id=user_id,
            query_text=query_text,
            top_k=3,
            memory_type="conversation_summary",
            conversation_id=None,
            only_active=True,
        )
    else:
        related_conversation_results = []
    logger.info(
        "Unified memory timing | stage=search_related_conversations | duration_min={}",
        elapsed_minutes(related_search_started_at),
    )

    profile_started_at = perf_counter()
    if context_policy.needs_user_profile:
        user_profile_text = await get_cached_user_profile_text(
            db,
            user_id=user_id,
            query_text=query_text,
        )
    else:
        user_profile_text = ""
    logger.info(
        "Unified memory timing | stage=get_cached_user_profile | duration_min={}",
        elapsed_minutes(profile_started_at),
    )

    context_assembly_started_at = perf_counter()
    ltm_context = build_ltm_context(ltm_results)
    if (
        context_policy.needs_user_profile
        and context_policy.needs_long_term_memory
        and not user_profile_text
        and ltm_context
    ):
        logger.info(
            "Unified memory identity fallback | profile_empty=True | using_ltm=True"
        )
    if context_policy.needs_related_conversations:
        related_conversations_context = build_related_conversations_context(
            related_conversation_results,
            current_conversation_id=conversation_id,
        )
    else:
        related_conversations_context = ""

    if context_policy.needs_conversation_metadata:
        metadata_context = build_metadata_context(conversation.convo_metadata)
    else:
        metadata_context = ""

    effective_rag_context = rag_context.strip() if context_policy.needs_file_context else ""
    combined_context = merge_contexts(
        effective_rag_context,
        metadata_context,
        user_profile_text,
        related_conversations_context,
        ltm_context,
    )

    logger.info(
        "Unified memory context mode | query_text={} | message_count={} | context_chars={}",
        query_text,
        len(raw_messages),
        len(combined_context),
    )
    logger.info(
        "Unified memory timing | stage=assemble_context_blocks | duration_min={}",
        elapsed_minutes(context_assembly_started_at),
    )

    stm_summary_started_at = perf_counter()
    stm_summary = get_stm_state(conversation.convo_metadata).get("rolling_summary", "")
    logger.info(
        "Unified memory timing | stage=get_stm_summary | duration_min={}",
        elapsed_minutes(stm_summary_started_at),
    )

    return UnifiedMemoryContext(
        messages=messages,
        stm_state=stm_state,
        stm_summary=stm_summary,
        context_policy=context_policy,
        ltm_results=ltm_results,
        related_conversation_results=related_conversation_results,
        conversation_metadata=conversation.convo_metadata or {},
        user_profile_text=user_profile_text,
        ltm_context=ltm_context,
        related_conversations_context=related_conversations_context,
        rag_context=effective_rag_context,
        combined_context=combined_context,
    )
