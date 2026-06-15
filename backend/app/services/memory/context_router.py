import json
import re
from dataclasses import dataclass

from app.models.message import Message
from app.services.llm import llm
from pydantic import BaseModel, Field, ConfigDict
from app.prompts import CONTEXT_ROUTER_USER_PROMPT, CONTEXT_ROUTER_SYSTEM_PROMPT



def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return default


def _coerce_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _message_to_line(message: Message) -> str:
    role = getattr(message, "role", "user")
    content = (getattr(message, "content", "") or "").strip()
    return f"{role}: {content}"


def _recent_history_excerpt(messages: list[Message], max_messages: int = 6) -> str:
    excerpt = [_message_to_line(message) for message in messages[-max_messages:]]
    return "\n".join(line for line in excerpt if line.strip())


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", (text or "").lower()))


def _contains_reference_signal(text: str) -> bool:
    lowered = f" {_normalize_text(text)} "
    referential_patterns = (
        " continue ",
        " again ",
        " earlier ",
        " before ",
        " previous ",
        " last time ",
        " you said ",
        " we said ",
        " that one ",
        " this one ",
        " what was that ",
        " as i said ",
        " as we discussed ",
        " back to ",
        " same thing ",
        " still ",
        " also ",
        " and ",
        " so ",
    )
    return any(pattern in lowered for pattern in referential_patterns)


def _contains_file_signal(text: str) -> bool:
    lowered = f" {_normalize_text(text)} "
    file_patterns = (
        " file ",
        " pdf ",
        " document ",
        " attachment ",
        " attached ",
        " image ",
        " screenshot ",
        " code ",
        " snippet ",
    )
    return any(pattern in lowered for pattern in file_patterns)


class ContextPolicy(BaseModel):
    needs_recent_history: bool
    needs_stm_summary: bool
    needs_file_context: bool
    needs_user_profile: bool
    needs_long_term_memory: bool
    needs_related_conversations: bool
    needs_conversation_metadata: bool

    is_self_contained: bool
    is_topic_shift: bool
    allow_temporary_modes: bool

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    model_config = ConfigDict(extra="forbid")


def _fallback_policy(
    *,
    query_text: str,
    recent_messages: list[Message],
    has_rag_context: bool,
) -> ContextPolicy:
    normalized_query = _normalize_text(query_text)
    token_count = len(normalized_query.split())
    has_reference_signal = _contains_reference_signal(query_text)
    has_file_signal = _contains_file_signal(query_text)
    is_first_turn = len(recent_messages) <= 1

    needs_recent_history = not is_first_turn and (has_reference_signal or token_count <= 4)
    needs_file_context = has_rag_context and has_file_signal
    needs_user_profile = False
    needs_long_term_memory = False
    is_self_contained = (
        not needs_recent_history
        and not needs_file_context
    )

    return ContextPolicy(
        needs_recent_history=needs_recent_history,
        needs_stm_summary=False,
        needs_file_context=needs_file_context,
        needs_user_profile=needs_user_profile,
        needs_long_term_memory=needs_long_term_memory,
        needs_related_conversations=False,
        needs_conversation_metadata=needs_recent_history and token_count <= 8,
        is_self_contained=is_self_contained,
        is_topic_shift=not is_first_turn and is_self_contained,
        allow_temporary_modes=has_reference_signal,
        confidence=0.35,
        reason="Fallback routing based on self-contained vs referential signals.",
    )


async def route_context_policy(
    *,
    query_text: str,
    recent_messages: list[Message],
    has_rag_context: bool,
) -> ContextPolicy:
    history_excerpt = _recent_history_excerpt(recent_messages)
    user_prompt=CONTEXT_ROUTER_USER_PROMPT.format(query_text=query_text.strip(), history_excerpt=history_excerpt)
    try:
        policy = await llm.structured(
            [   {"role": "system", "content": CONTEXT_ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            purpose="context_routing",
            response_model=ContextPolicy,
        )
        # policy = ContextPolicy.model_validate_json(response)
    except Exception:
        return _fallback_policy(
            query_text=query_text,
            recent_messages=recent_messages,
            has_rag_context=has_rag_context,
        )

    # policy = ContextPolicy(
    #     needs_recent_history=_as_bool(parsed.get("needs_recent_history"), True),
    #     needs_stm_summary=_as_bool(parsed.get("needs_stm_summary"), False),
    #     needs_file_context=_as_bool(parsed.get("needs_file_context"), False) and has_rag_context,
    #     needs_user_profile=_as_bool(parsed.get("needs_user_profile"), False),
    #     needs_long_term_memory=_as_bool(parsed.get("needs_long_term_memory"), False),
    #     needs_related_conversations=_as_bool(parsed.get("needs_related_conversations"), False),
    #     needs_conversation_metadata=_as_bool(parsed.get("needs_conversation_metadata"), False),
    #     is_self_contained=_as_bool(parsed.get("is_self_contained"), False),
    #     is_topic_shift=_as_bool(parsed.get("is_topic_shift"), False),
    #     allow_temporary_modes=_as_bool(parsed.get("allow_temporary_modes"), False),
    #     confidence=_coerce_confidence(parsed.get("confidence")),
    #     reason=str(parsed.get("reason", "")).strip(),
    # )

    if policy.is_self_contained:
        policy.needs_long_term_memory = False
        policy.needs_related_conversations = False
        if not policy.needs_file_context:
            policy.needs_user_profile = False

    if policy.is_topic_shift:
        policy.allow_temporary_modes = False
        policy.needs_related_conversations = False

    return policy
