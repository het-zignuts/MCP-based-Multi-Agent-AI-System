from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from time import perf_counter

from app.models import Message
from app.schemas.message import MessageCreate
from app.crud.message import create_message
from app.crud.conversation import get_conversation, update_conversation_metadata
from app.services.llm import llm
from app.services.rag.retriever import retrieve_pipeline
from app.services.memory.unified_memory_service import build_unified_memory_context
from app.services.memory.memory_services import set_stm_state
from app.services.time.timing import elapsed_minutes, log_async_timing
from app.services.tokenization.token_service import get_message_token_count
from app.prompts import CHAT_SYSTEM_PROMPT
from app.services.memory.background_memory_pipeline import (
    schedule_memory_maintenance_pipeline,
)
from app.services.user_profile.user_profile_cache_service import (
    update_profile_snapshot_from_user_message,
)
from app.services.file_generation.intent_router import (
    classify_generation_intent_with_llm,
    detect_generation_intent,
)
from app.services.file_generation.file_generation_service import generate_file_artifact
from app.agent_layer.agents.root_agent import RootAgent
from app.agent_layer.schemas import AgentContext

root_agent = RootAgent()

EMPTY_RESPONSE_FALLBACK = (
    "I lost the thread for a moment. Please repeat the last line you want me to continue from, "
    "and I'll pick it up directly."
)


def build_message_history(
    messages: list[Message],
    rag_context: str = "",
) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
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

def parse_latest_message(content: str) -> tuple[str, str, str]:
    context_marker = "\n\nRelevant context:\n"
    attachment_marker = "\n\nAttached files:\n"

    if context_marker in content:
        user_portion, context = content.split(context_marker, 1)
    else:
        user_portion = content
        context = ""

    if attachment_marker in user_portion:
        user_query, attached_files = user_portion.split(attachment_marker, 1)
    else:
        user_query = user_portion
        attached_files = ""

    return user_query.strip(), attached_files.strip(), context.strip()

def build_llm_messages(
    history: list[dict[str, str]],
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    system_content = system_prompt or CHAT_SYSTEM_PROMPT
    if not history:
        return [{"role": "system", "content": system_content}]

    messages = [{"role": "system", "content": system_content}]

    for message in history[:-1]:
        messages.append(
            {
                "role": message["role"],
                "content": message["content"].strip(),
            }
        )

    user_query, attached_files, context = parse_latest_message(history[-1]["content"])

    final_sections = [f"User question:\n{user_query}"]
    if attached_files:
        final_sections.append(f"Attached files:\n{attached_files}")
    if context:
        final_sections.append(f"Relevant context:\n{context}")

    messages.append(
        {
            "role": history[-1]["role"],
            "content": "\n\n".join(final_sections),
        }
    )
    return messages

@log_async_timing("generate_ai_response")
async def generate_ai_response(
    messages: list[Message],
    rag_context: str = "",
) -> str:
    history = build_message_history(messages, rag_context=rag_context)
    if history:
        logger.info("Final prompt roles | roles={}", [message["role"] for message in history])
        logger.info("Final prompt last message | content={}", history[-1]["content"])
    messages=build_llm_messages(history, system_prompt=CHAT_SYSTEM_PROMPT)
    response = await llm.chat(
        messages=messages,
        purpose="chat_response",
    )
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


# def merge_conversation_metadata(existing_metadata: dict | None, new_metadata: dict) -> dict:
#     metadata = dict(existing_metadata or {})
#     stm_data = metadata.get("stm")

#     merged_topics = sorted(set((metadata.get("topics") or []) + (new_metadata.get("topics") or [])))
#     merged_entities = sorted(set((metadata.get("entities") or []) + (new_metadata.get("entities") or [])))
#     merged_goals = sorted(set((metadata.get("active_goals") or []) + (new_metadata.get("active_goals") or [])))

#     metadata["topics"] = merged_topics
#     metadata["entities"] = merged_entities
#     metadata["active_goals"] = merged_goals
#     metadata["sentiment"] = new_metadata.get("sentiment", metadata.get("sentiment", "neutral"))
#     metadata["summary_hint"] = new_metadata.get("summary_hint", metadata.get("summary_hint", ""))

#     if stm_data is not None:
#         metadata["stm"] = stm_data

#     return metadata


@log_async_timing("send_message")
async def send_message(
    db: AsyncSession,
    payload: MessageCreate,
    rag_context: str = "",
)-> dict[str, Message]:
    turn_started_at = perf_counter()
    payload.token_count = get_message_token_count(payload)

    create_user_started_at = perf_counter()
    user_message = await create_message(db, payload)
    logger.info(
        "Chat timing | stage=create_user_message | duration_min={}",
        elapsed_minutes(create_user_started_at),
    )

    profile_update_started_at = perf_counter()
    await update_profile_snapshot_from_user_message(
        db,
        user_message=user_message,
    )
    logger.info(
        "Chat timing | stage=update_profile_snapshot | duration_min={}",
        elapsed_minutes(profile_update_started_at),
    )

    unified_memory_started_at = perf_counter()
    unified_memory = await build_unified_memory_context(
        db,
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        query_text=payload.content,
        rag_context=rag_context,
    )
    logger.info(
        "Chat timing | stage=build_unified_memory_context | duration_min={}",
        elapsed_minutes(unified_memory_started_at),
    )

    conversation = await get_conversation(db, payload.conversation_id)
    update_stm_started_at = perf_counter()
    updated_metadata = set_stm_state(conversation.convo_metadata, unified_memory.stm_state)
    await update_conversation_metadata(
        db,
        payload.conversation_id,
        updated_metadata,
    )
    logger.info(
        "Chat timing | stage=update_stm_state | duration_min={}",
        elapsed_minutes(update_stm_started_at),
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

    # ai_response_started_at = perf_counter()
    # ai_content = await generate_ai_response(
    #     unified_memory.messages,
    #     rag_context=unified_memory.combined_context,
    # )

    agent_context = AgentContext(
        user_id=str(payload.user_id),
        conversation_id=str(payload.conversation_id),
        user_message=payload.content,

        stm_context=unified_memory.stm_summary if unified_memory.context_policy.needs_stm_summary else "",
        ltm_context=unified_memory.ltm_context if unified_memory.context_policy.needs_long_term_memory else "",
        profile_context=unified_memory.user_profile_text if unified_memory.context_policy.needs_user_profile else "",
        rag_context=unified_memory.effective_rag_context if unified_memory.context_policy.needs_file_context else "",
        conversation_metadata=conversation.convo_metadata if unified_memory.context_policy.needs_conversation_metadata else {},
        )

    agent_response = await root_agent.run(agent_context)
    ai_content = agent_response.content
    logger.info(
            "Chat timing | stage=generate_ai_response | duration_min={}",
            elapsed_minutes(ai_response_started_at),
        )
    if not ai_content:
        ai_content = EMPTY_RESPONSE_FALLBACK

    ai_message = build_ai_message_payload(
        user_message,
        ai_content,
        file_ids=payload.file_ids,
    )
    ai_message.token_count = get_message_token_count(ai_message)
    create_ai_started_at = perf_counter()
    ai_message = await create_message(db, ai_message)
    logger.info(
        "Chat timing | stage=create_ai_message | duration_min={}",
        elapsed_minutes(create_ai_started_at),
    )
        

    schedule_maintenance_started_at = perf_counter()
    schedule_memory_maintenance_pipeline(
        user_id=payload.user_id,
        conversation_id=payload.conversation_id,
    )
    logger.info(
        "Chat timing | stage=schedule_memory_maintenance | duration_min={}",
        elapsed_minutes(schedule_maintenance_started_at),
    )

    logger.info(
        "Chat timing | stage=total_turn | duration_min={}",
        elapsed_minutes(turn_started_at),
    )
    return {
        "user_message": user_message,
        "ai_message": ai_message,
    }
    

@log_async_timing("send_message_from_payload")
async def send_message_from_payload(
    db: AsyncSession,
    conversation_id,
    payload: dict,
    authenticated_user_id,
)-> dict[str, Message]:
    request_started_at = perf_counter()
    generation_decision = detect_generation_intent(
        text=payload["content"],
        explicit_format=payload.get("format"),
        explicit_action=payload.get("action"),
    )

    if not generation_decision.should_generate:
        generation_decision = await classify_generation_intent_with_llm(
            text=payload["content"],
            current_decision=generation_decision,
        )
        logger.info("Using LLM for intent detection | should_generate=%s | reason=%s", generation_decision.should_generate, generation_decision.reason)

    if generation_decision.should_generate:
        generated = await generate_file_artifact(
            db,
            user_id=authenticated_user_id,
            conversation_id=conversation_id,
            prompt=payload["content"],
            output_format=payload.get("format") or generation_decision.format,
            file_ids=payload.get("file_ids", []),
            decision=generation_decision,
            explicit_action=payload.get("action"),
            persist_messages=True,
        )
        logger.info(
            "Chat timing | stage=generate_file_artifact | duration_min={}",
            elapsed_minutes(request_started_at),
        )
        return {
            "user_message": generated.user_message,
            "ai_message": generated.assistant_message,
        }

    message_payload = MessageCreate(
        user_id=authenticated_user_id,
        conversation_id=conversation_id,
        content=payload["content"],
        role="user",
        token_count=None,
        file_ids=payload.get("file_ids", []),
    )

    logger.info("Incoming message file IDs | file_ids={}", message_payload.file_ids)

    rag_started_at = perf_counter()
    rag_context = await retrieve_pipeline(
        payload["content"],
        message_payload.file_ids or [],
        conversation_id,
        authenticated_user_id,
        db,
    )

    logger.info("Retrieved RAG context | has_context={}", bool(rag_context))
    logger.info(
        "Chat timing | stage=retrieve_pipeline | duration_min={}",
        elapsed_minutes(rag_started_at),
    )

    result = await send_message(
        db,
        message_payload,
        rag_context=rag_context,
    )
    logger.info(
        "Chat timing | stage=send_message_from_payload_total | duration_min={}",
        elapsed_minutes(request_started_at),
    )
    return result
