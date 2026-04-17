from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.conversation import get_conversation
from app.crud.memory import get_recent_memories_by_type
from app.services.memory.ltm_service import ComparisonBudget, create_memory_with_embedding
from app.services.memory_services import get_stm_state


async def promote_conversation_summary_to_ltm(
    db: AsyncSession,
    *,
    conversation_id,
    user_id,
    comparison_budget: ComparisonBudget | None = None,
) -> dict | None:
    conversation = await get_conversation(db, conversation_id)
    convo_metadata = conversation.convo_metadata or {}

    stm_state = get_stm_state(convo_metadata)
    rolling_summary = stm_state.get("rolling_summary", "").strip()

    if not rolling_summary:
        return None

    topics = convo_metadata.get("topics", [])
    entities = convo_metadata.get("entities", [])
    active_goals = convo_metadata.get("active_goals", [])
    summary_hint = convo_metadata.get("summary_hint", "")

    summary_content_parts = [rolling_summary]

    if summary_hint:
        summary_content_parts.append(f"Focus: {summary_hint}")
    if topics:
        summary_content_parts.append("Topics: " + ", ".join(topics))
    if entities:
        summary_content_parts.append("Entities: " + ", ".join(entities))
    if active_goals:
        summary_content_parts.append("Active goals: " + "; ".join(active_goals))

    summary_content = "\n".join(summary_content_parts).strip()
    if not summary_content:
        return None

    recent_summaries = await get_recent_memories_by_type(
        db,
        user_id=user_id,
        memory_type="conversation_summary",
        limit=5,
        only_active=True,
    )
    for existing_summary in recent_summaries:
        if (
            existing_summary.conversation_id == conversation_id
            and (existing_summary.content or "").strip() == summary_content
        ):
            return {
                "id": str(existing_summary.id),
                "content": existing_summary.content,
                "memory_type": existing_summary.memory_type,
            }

    memory = await create_memory_with_embedding(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        content=summary_content,
        memory_type="conversation_summary",
        memory_metadata={
            "source": "conversation_summary",
            "topics": topics,
            "entities": entities,
            "active_goals": active_goals,
            "summary_hint": summary_hint,
        },
        importance_score=0.85,
        source="conversation_summary",
        comparison_budget=comparison_budget,
    )

    if memory is None:
        return None

    return {
        "id": str(memory.id),
        "content": memory.content,
        "memory_type": memory.memory_type,
    }
