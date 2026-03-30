from app.services.tokenization.tokenizer import get_token_count


def get_message_token_count(message) -> int:
    cached_token_count = getattr(message, "token_count", None)
    if cached_token_count is not None:
        return cached_token_count

    return get_token_count(getattr(message, "content", ""))


def build_token_limited_history(messages, max_tokens=3000, preserve_recent_messages=6):
    selected = []
    total_tokens = 0

    recent_messages = (
        list(messages[-preserve_recent_messages:])
        if preserve_recent_messages > 0
        else []
    )
    recent_message_keys = {
        getattr(message, "id", None) or id(message)
        for message in recent_messages
    }

    # Always keep the most recent messages first, even if they alone exceed budget.
    for msg in recent_messages:
        selected.append(msg)
        total_tokens += get_message_token_count(msg)

    # Fill remaining budget with older messages from newest to oldest.
    older_messages = messages[: len(messages) - len(recent_messages)]
    for msg in reversed(older_messages):
        tokens = get_message_token_count(msg)
        if total_tokens + tokens > max_tokens:
            continue
        selected.insert(0, msg)
        total_tokens += tokens

    selected_keys = {
        getattr(message, "id", None) or id(message)
        for message in selected
    }
    dropped = [
        message
        for message in messages
        if (getattr(message, "id", None) or id(message)) not in selected_keys
    ]

    # If duplicates ever appear, favor the later kept copy and avoid dropping preserved recency.
    if recent_message_keys:
        dropped = [
            message
            for message in dropped
            if (getattr(message, "id", None) or id(message)) not in recent_message_keys
        ]

    return selected, dropped
