from dataclasses import dataclass

from loguru import logger

from app.services.tokenization.token_service import build_token_limited_history
from app.models.message import Message
from app.services.summarization.summarization_service import (
    is_valid_summary,
    normalize_summary,
    summarize_messages,
)
from app.services.time.timing import log_async_timing

SUMMARY_TOKEN_BUDGET = 1000
RAW_HISTORY_TOKEN_BUDGET = 2600
PRESERVE_RECENT_MESSAGES = 10
PRESERVE_RECENT_TURNS = 5
SUMMARY_REFRESH_INTERVAL = 4


@dataclass
class StmContext:
    recent_messages: list[Message]
    rolling_summary: str
    dropped_messages: list[Message]
    token_usage: int
    dropped_count: int
    summary_updated: bool


def get_stm_state(convo_metadata: dict | None) -> dict:
    if not convo_metadata:
        return {}
    stm_state = convo_metadata.get("stm")
    if isinstance(stm_state, dict):
        return stm_state
    return {}


def set_stm_state(convo_metadata: dict | None, stm_state: dict) -> dict:
    metadata = dict(convo_metadata or {})
    metadata["stm"] = stm_state
    return metadata


def build_summary_message(rolling_summary: str) -> Message | None:
    if not rolling_summary:
        return None
    return Message(
        role="system",
        content=(
            "Compressed memory from earlier conversation.\n"
            "Use it only as background context. Prefer the newer raw messages when they conflict.\n"
            "Do not switch into meta commentary just because this summary exists.\n\n"
            f"{rolling_summary}"
        ),
    )


@log_async_timing("build_stm_context")
async def build_stm_context(
    messages,
    existing_summary: str = "",
    summary_update_count: int = 0,
    max_tokens=3600,
):
    regular_messages = list(messages)

    raw_budget = min(RAW_HISTORY_TOKEN_BUDGET, max_tokens)
    if max_tokens > SUMMARY_TOKEN_BUDGET:
        raw_budget = min(raw_budget, max_tokens - SUMMARY_TOKEN_BUDGET)

    selected, dropped = build_token_limited_history(
        regular_messages,
        max_tokens=raw_budget,
        preserve_recent_messages=PRESERVE_RECENT_MESSAGES,
        preserve_recent_turns=PRESERVE_RECENT_TURNS,
    )

    next_summary = existing_summary
    summary_updated = False
    if dropped:
        summary_source_messages = dropped
        if summary_update_count and summary_update_count % SUMMARY_REFRESH_INTERVAL == 0:
            summary_source_messages = regular_messages[:-len(selected)] if selected else regular_messages

        raw_candidate_summary = await summarize_messages(
            summary_source_messages,
            existing_summary=existing_summary,
        )
        candidate_summary = normalize_summary(raw_candidate_summary)
        logger.info(
            "STM summary candidate | dropped_count={} | normalized_chars={} | raw_preview={}",
            len(dropped),
            len(candidate_summary),
            (raw_candidate_summary or "")[:300],
        )
        if is_valid_summary(candidate_summary):
            next_summary = candidate_summary
            summary_updated = True
        else:
            logger.warning(
                "STM summary rejected | dropped_count={} | raw_preview={}",
                len(dropped),
                (raw_candidate_summary or "")[:300],
            )

    token_usage = sum(getattr(message, "token_count", 0) or 0 for message in selected)

    return StmContext(
        recent_messages=selected,
        rolling_summary=next_summary,
        dropped_messages=dropped,
        token_usage=token_usage,
        dropped_count=len(dropped),
        summary_updated=summary_updated,
    )


@log_async_timing("build_smart_history")
async def build_smart_history(messages, convo_metadata: dict | None = None, max_tokens=3600):
    stm_state = get_stm_state(convo_metadata)
    stm_context = await build_stm_context(
        messages,
        existing_summary=stm_state.get("rolling_summary", ""),
        summary_update_count=stm_state.get("summary_update_count", 0),
        max_tokens=max_tokens,
    )

    next_update_count = stm_state.get("summary_update_count", 0)
    if stm_context.summary_updated:
        next_update_count += 1

    updated_stm_state = {
        "rolling_summary": stm_context.rolling_summary,
        "summary_update_count": next_update_count,
        "last_token_usage": stm_context.token_usage,
        "last_dropped_count": stm_context.dropped_count,
        "recent_message_count": len(stm_context.recent_messages),
    }

    history_messages = list(stm_context.recent_messages)
    summary_message = build_summary_message(stm_context.rolling_summary)
    if summary_message:
        history_messages = [summary_message] + history_messages

    return history_messages, updated_stm_state, stm_context
