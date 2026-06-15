AGENT_STATE_KEY = "agent_state"


def get_agent_state(
    metadata: dict | None,
) -> dict:

    metadata = metadata or {}

    return metadata.get(
        AGENT_STATE_KEY,
        {
            "active_agent": "general",
            "last_agent": None,
        },
    )


def set_active_agent(
    metadata: dict | None,
    agent_name: str,
) -> dict:

    metadata = dict(metadata or {})

    state = get_agent_state(metadata)

    state["last_agent"] = state.get("active_agent")
    state["active_agent"] = agent_name

    metadata[AGENT_STATE_KEY] = state

    return metadata