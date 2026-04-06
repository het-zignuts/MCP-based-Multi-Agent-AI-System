from app.services.tokenization.tokenizer import get_token_count


def get_message_token_count(message) -> int:
    cached_token_count = getattr(message, "token_count", None)
    if cached_token_count is not None:
        return cached_token_count

    return get_token_count(getattr(message, "content", ""))


def _select_recent_turn_messages(messages, preserve_recent_turns=4):
    if preserve_recent_turns <= 0 or not messages:
        return []

    user_turns_seen = 0
    boundary_index = len(messages)

    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        boundary_index = index
        if getattr(message, "role", None) == "user":
            user_turns_seen += 1
            if user_turns_seen >= preserve_recent_turns:
                break

    return list(messages[boundary_index:])


def build_token_limited_history(
    messages,
    max_tokens=3000,
    preserve_recent_messages=6,
    preserve_recent_turns=4,
):
    recent_turn_messages = _select_recent_turn_messages(
        messages,
        preserve_recent_turns=preserve_recent_turns,
    )
    recent_messages = list(recent_turn_messages)
    if preserve_recent_messages > 0:
        trailing_messages = list(messages[-preserve_recent_messages:])
        trailing_message_keys = {
            getattr(message, "id", None) or id(message)
            for message in trailing_messages
        }
        recent_message_keys = {
            getattr(message, "id", None) or id(message)
            for message in recent_messages
        }
        for message in trailing_messages:
            message_key = getattr(message, "id", None) or id(message)
            if message_key not in recent_message_keys:
                recent_messages.append(message)
                recent_message_keys.add(message_key)

    recent_message_keys = {
        getattr(message, "id", None) or id(message)
        for message in recent_messages
    }

    if recent_messages:
        boundary_index = next(
            index
            for index, message in enumerate(messages)
            if (getattr(message, "id", None) or id(message)) in recent_message_keys
        )
    else:
        boundary_index = len(messages)

    selected = list(messages[boundary_index:])
    total_tokens = sum(get_message_token_count(message) for message in selected)

    # Keep a contiguous window by only prepending immediately older messages while they fit.
    prepend_index = boundary_index - 1
    while prepend_index >= 0:
        message = messages[prepend_index]
        tokens = get_message_token_count(message)
        if total_tokens + tokens > max_tokens:
            break
        selected.insert(0, message)
        total_tokens += tokens
        prepend_index -= 1

    dropped = list(messages[: prepend_index + 1])
    return selected, dropped
