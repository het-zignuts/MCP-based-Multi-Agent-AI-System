from app.services.tokenization.token_service import build_token_limited_history
from app.db.models.message import Message
from app.services.summarization.summarization_service import summarize_messages

SUMMARY_TOKEN_BUDGET = 1000
RAW_HISTORY_TOKEN_BUDGET = 2600
PRESERVE_RECENT_MESSAGES = 10
SUMMARY_PREFIX = "Summary of earlier conversation:\n"


def _is_summary_message(message: Message) -> bool:
    return (
        getattr(message, "role", None) == "system"
        and getattr(message, "content", "").startswith(SUMMARY_PREFIX)
    )


def _split_summary_from_messages(messages: list[Message]) -> tuple[str, list[Message]]:
    summary_parts = []
    regular_messages = []

    for message in messages:
        if _is_summary_message(message):
            summary_parts.append(message.content[len(SUMMARY_PREFIX):].strip())
        else:
            regular_messages.append(message)

    merged_summary = "\n\n".join(part for part in summary_parts if part)
    return merged_summary, regular_messages


async def build_smart_history(messages, max_tokens=3600):
    existing_summary, regular_messages = _split_summary_from_messages(messages)

    raw_budget = min(RAW_HISTORY_TOKEN_BUDGET, max_tokens)
    if max_tokens > SUMMARY_TOKEN_BUDGET:
        raw_budget = min(raw_budget, max_tokens - SUMMARY_TOKEN_BUDGET)

    selected, dropped = build_token_limited_history(
        regular_messages,
        max_tokens=raw_budget,
        preserve_recent_messages=PRESERVE_RECENT_MESSAGES,
    )

    next_summary = existing_summary
    if len(dropped) > 0:
        next_summary = await summarize_messages(
            dropped,
            existing_summary=existing_summary,
        )
    elif existing_summary:
        next_summary = existing_summary

    if next_summary:
        summary_message = Message(
            role="system",
            content=f"{SUMMARY_PREFIX}{next_summary}"
        )
        selected = [summary_message] + selected

    return selected
