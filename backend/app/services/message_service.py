from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import Message
from app.schemas.message import MessageCreate
from app.crud.message import create_message
from app.crud.conversation import get_conversation, update_conversation_metadata
from app.services.llm_service import get_llm_response_async
from app.services.rag.retriever import retrieve_pipeline
from app.services.memory.conversation_metadata_extractor import extract_conversation_metadata
from app.services.memory.memory_promoter import (
    promote_memories_from_messages,
    messages_to_conversation_text,
)
from app.services.memory.conversation_summary_memory_service import (
    promote_conversation_summary_to_ltm,
)
from app.services.memory.history_service import fetch_conversation_history
from app.services.memory.lifecycle_service import maintain_memory_lifecycle
from app.services.memory.unified_memory_service import build_unified_memory_context
from app.services.memory_services import set_stm_state
from app.services.tokenization.token_service import get_message_token_count


EMPTY_RESPONSE_FALLBACK = (
    "I lost the thread for a moment. Please repeat the last line you want me to continue from, "
    "and I'll pick it up directly."
)


def build_message_history(
    messages: list[Message],
    rag_context: str = "",
) -> list[dict[str, str]]:
    history = []
    for message in messages:
        attached_files = getattr(message, "files", []) or []
        file_lines = [
            f"- {file.filename} ({file.status})"
            for file in attached_files
        ]
        file_block = ""
        if file_lines:
            file_block = "\n\nAttached files:\n" + "\n".join(file_lines)

        history.append(
            {
                "role": message.role,
                "content": f"{message.content}{file_block}",
            }
        )

    logger.info("RAG/LTM context attached | has_context={}", bool(rag_context))

    if rag_context and history:
        last_message = history[-1]
        history[-1] = {
            **last_message,
            "content": (
                f"{last_message['content']}\n\n"
                f"Relevant context:\n{rag_context}"
            ),
        }

    return history


async def generate_ai_response(
    messages: list[Message],
    rag_context: str = "",
) -> str:
    history = build_message_history(messages, rag_context=rag_context)
    if history:
        logger.info("Final prompt roles | roles={}", [message["role"] for message in history])
        logger.info("Final prompt last message | content={}", history[-1]["content"])
    response = await get_llm_response_async(history)
    return (response or "").strip()


def build_ai_message_payload(
    user_message: Message,
    ai_content: str,
    file_ids: list | None = None,
) -> MessageCreate:
    return MessageCreate(
        user_id=user_message.user_id,
        conversation_id=user_message.conversation_id,
        content=ai_content,
        role="assistant",
        token_count=None,
        file_ids=file_ids or [],
    )


def merge_conversation_metadata(existing_metadata: dict | None, new_metadata: dict) -> dict:
    metadata = dict(existing_metadata or {})
    stm_data = metadata.get("stm")

    merged_topics = sorted(set((metadata.get("topics") or []) + (new_metadata.get("topics") or [])))
    merged_entities = sorted(set((metadata.get("entities") or []) + (new_metadata.get("entities") or [])))
    merged_goals = sorted(set((metadata.get("active_goals") or []) + (new_metadata.get("active_goals") or [])))

    metadata["topics"] = merged_topics
    metadata["entities"] = merged_entities
    metadata["active_goals"] = merged_goals
    metadata["sentiment"] = new_metadata.get("sentiment", metadata.get("sentiment", "neutral"))
    metadata["summary_hint"] = new_metadata.get("summary_hint", metadata.get("summary_hint", ""))

    if stm_data is not None:
        metadata["stm"] = stm_data

    return metadata


async def send_message(
    db: AsyncSession,
    payload: MessageCreate,
    rag_context: str = "",
):
    payload.token_count = get_message_token_count(payload)

    user_message = await create_message(db, payload)

    unified_memory = await build_unified_memory_context(
        db,
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        query_text=payload.content,
        rag_context=rag_context,
    )

    conversation = await get_conversation(db, payload.conversation_id)
    updated_metadata = set_stm_state(conversation.convo_metadata, unified_memory.stm_state)
    await update_conversation_metadata(
        db,
        payload.conversation_id,
        updated_metadata,
    )

    logger.info("STM state | state={}", unified_memory.stm_state)
    logger.info("Retrieved LTM memories | count={}", len(unified_memory.ltm_results))
    logger.info(
        "User profile context ready | has_profile={}",
        bool(unified_memory.user_profile_text),
    )

    logger.info(
        "Unified context ready | has_context={}",
        bool(unified_memory.combined_context),
    )

    ai_content = await generate_ai_response(
        unified_memory.messages,
        rag_context=unified_memory.combined_context,
    )
    if not ai_content:
        ai_content = EMPTY_RESPONSE_FALLBACK

    ai_message = build_ai_message_payload(
        user_message,
        ai_content,
        file_ids=payload.file_ids,
    )
    ai_message.token_count = get_message_token_count(ai_message)
    ai_message = await create_message(db, ai_message)

    updated_messages = await fetch_conversation_history(
        db,
        payload.conversation_id,
        limit=20,
    )

    try:
        promoted_memories = await promote_memories_from_messages(
            db,
            user_id=payload.user_id,
            messages=updated_messages,
            conversation_id=payload.conversation_id,
            source="conversation",
        )
        logger.info("LTM promotion complete | created_count={}", len(promoted_memories))

        lifecycle_result = await maintain_memory_lifecycle(
            db,
            user_id=payload.user_id,
            candidate_memory_ids=[
                item["id"]
                for item in promoted_memories
                if item.get("id")
            ],
        )
        logger.info(
            "Memory lifecycle maintenance complete | resolved_conflicts={} | pruned_memories={}",
            lifecycle_result["resolved_conflicts"],
            lifecycle_result["pruned_memories"],
        )
    except Exception:
        logger.exception("LTM promotion failed for conversation {}", payload.conversation_id)

    try:
        conversation_text = messages_to_conversation_text(updated_messages)
        extracted_metadata = await extract_conversation_metadata(conversation_text)

        refreshed_conversation = await get_conversation(db, payload.conversation_id)
        merged_metadata = merge_conversation_metadata(
            refreshed_conversation.convo_metadata,
            extracted_metadata,
        )

        await update_conversation_metadata(
            db,
            payload.conversation_id,
            merged_metadata,
        )
        logger.info(
            "Conversation metadata updated | topics={} | entities={} | goals={}",
            len(merged_metadata.get("topics", [])),
            len(merged_metadata.get("entities", [])),
            len(merged_metadata.get("active_goals", [])),
        )
    except Exception:
        logger.exception("Conversation metadata extraction failed for conversation {}", payload.conversation_id)
    try:
        summary_memory = await promote_conversation_summary_to_ltm(
            db,
            conversation_id=payload.conversation_id,
            user_id=payload.user_id,
        )
        logger.info(
            "Conversation summary promotion complete | created={}",
            bool(summary_memory),
        )
    except Exception:
        logger.exception(
            "Conversation summary promotion failed for conversation {}",
            payload.conversation_id,
        )
    return {
        "user_message": user_message,
        "ai_message": ai_message,
    }


async def send_message_from_payload(
    db: AsyncSession,
    conversation_id,
    payload: dict,
    authenticated_user_id,
):
    message_payload = MessageCreate(
        user_id=authenticated_user_id,
        conversation_id=conversation_id,
        content=payload["content"],
        role="user",
        token_count=None,
        file_ids=payload.get("file_ids", []),
    )

    logger.info("Incoming message file IDs | file_ids={}", message_payload.file_ids)

    rag_context = await retrieve_pipeline(
        payload["content"],
        message_payload.file_ids or [],
        conversation_id,
        authenticated_user_id,
        db,
    )

    logger.info("Retrieved RAG context | has_context={}", bool(rag_context))

    return await send_message(
        db,
        message_payload,
        rag_context=rag_context,
    )
