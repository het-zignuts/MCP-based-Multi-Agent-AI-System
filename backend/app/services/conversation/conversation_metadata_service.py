def merge_conversation_metadata(existing_metadata: dict | None, new_metadata: dict) -> dict:
    metadata = dict(existing_metadata or {})
    stm_data = metadata.get("stm")

    merged_topics = sorted(set((metadata.get("topics") or []) + (new_metadata.get("topics") or [])))
    merged_entities = sorted(set((metadata.get("entities") or []) + (new_metadata.get("entities") or [])))
    current_goals = [
        goal
        for goal in (new_metadata.get("active_goals") or [])
        if str(goal).strip()
    ]

    metadata["topics"] = merged_topics
    metadata["entities"] = merged_entities
    metadata["active_goals"] = current_goals
    metadata["sentiment"] = new_metadata.get("sentiment", metadata.get("sentiment", "neutral"))
    metadata["summary_hint"] = new_metadata.get("summary_hint", metadata.get("summary_hint", ""))

    if stm_data is not None:
        metadata["stm"] = stm_data

    return metadata
