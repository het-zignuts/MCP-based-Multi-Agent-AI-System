from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.conversation import get_conversation
from app.services.memory.history_service import fetch_conversation_history
from app.services.memory.ltm_service import search_memories_with_scores
from app.services.memory.user_profile_service import build_user_profile
from app.services.memory_services import build_smart_history, get_stm_state


@dataclass
class UnifiedMemoryContext:
    messages: list
    stm_state: dict
    stm_summary: str
    ltm_results: list[dict]
    related_conversation_results: list[dict]
    conversation_metadata: dict
    user_profile_text: str
    ltm_context: str
    related_conversations_context: str
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
    conversation = await get_conversation(db, conversation_id)

    raw_messages = await fetch_conversation_history(
        db,
        conversation_id,
        limit=history_limit,
    )

    messages, stm_state, _ = await build_smart_history(
        raw_messages,
        convo_metadata=conversation.convo_metadata,
    )

    all_ltm_results = await search_memories_with_scores(
        db,
        user_id=user_id,
        query_text=query_text,
        top_k=max(ltm_top_k * 2, 6),
        conversation_id=None,
        only_active=True,
    )
    ltm_results = [
        item
        for item in all_ltm_results
        if item["memory"].memory_type != "conversation_summary"
    ][:ltm_top_k]

    related_conversation_results = await search_memories_with_scores(
        db,
        user_id=user_id,
        query_text=query_text,
        top_k=3,
        memory_type="conversation_summary",
        conversation_id=None,
        only_active=True,
    )

    user_profile = await build_user_profile(
        db,
        user_id=user_id,
    )
    user_profile_text = user_profile.to_text()

    ltm_context = build_ltm_context(ltm_results)
    related_conversations_context = build_related_conversations_context(
        related_conversation_results,
        current_conversation_id=conversation_id,
    )
    metadata_context = build_metadata_context(conversation.convo_metadata)
    combined_context = merge_contexts(
        rag_context,
        metadata_context,
        user_profile_text,
        related_conversations_context,
        ltm_context,
    )

    stm_summary = get_stm_state(conversation.convo_metadata).get("rolling_summary", "")

    return UnifiedMemoryContext(
        messages=messages,
        stm_state=stm_state,
        stm_summary=stm_summary,
        ltm_results=ltm_results,
        related_conversation_results=related_conversation_results,
        conversation_metadata=conversation.convo_metadata or {},
        user_profile_text=user_profile_text,
        ltm_context=ltm_context,
        related_conversations_context=related_conversations_context,
        combined_context=combined_context,
    )
