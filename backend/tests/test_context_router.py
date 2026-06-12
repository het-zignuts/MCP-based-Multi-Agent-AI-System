from app.services.memory.context_router import _contains_identity_signal, _fallback_policy
from  app.services.conversation.conversation_metadata_service import merge_conversation_metadata
from app.services.memory.unified_memory_service import filter_messages_for_policy
from app.services.memory.context_router import ContextPolicy
from app.services.user_profile.user_profile_service import _is_identity_fact_text


def test_fallback_policy_keeps_self_contained_turns_memory_light():
    policy = _fallback_policy(
        query_text="Hey",
        recent_messages=[],
        has_rag_context=False,
    )

    assert policy.needs_recent_history is False
    assert policy.needs_long_term_memory is False
    assert policy.needs_related_conversations is False
    assert policy.needs_user_profile is False
    assert policy.is_self_contained is True


def test_fallback_policy_detects_referential_turns():
    policy = _fallback_policy(
        query_text="What was that earlier point again?",
        recent_messages=[object(), object()],
        has_rag_context=False,
    )

    assert policy.needs_recent_history is True
    assert policy.allow_temporary_modes is True
    assert policy.is_self_contained is False


def test_fallback_policy_uses_profile_and_ltm_for_identity_queries():
    policy = _fallback_policy(
        query_text="What is my name?",
        recent_messages=[object()],
        has_rag_context=False,
    )

    assert policy.needs_user_profile is True
    assert policy.needs_long_term_memory is True
    assert policy.is_self_contained is False


def test_identity_signal_detects_name_queries():
    assert _contains_identity_signal("What's my name?") is True
    assert _contains_identity_signal("Who am I?") is True
    assert _contains_identity_signal("Tell me a joke") is False


def test_merge_conversation_metadata_replaces_stale_active_goals():
    merged = merge_conversation_metadata(
        {
            "topics": ["platypus"],
            "entities": ["pgvector"],
            "active_goals": ["Provide platypus facts"],
            "sentiment": "neutral",
            "summary_hint": "Old focus",
        },
        {
            "topics": ["emotional support"],
            "entities": ["family"],
            "active_goals": ["Talk through relationship uncertainty"],
            "sentiment": "mixed",
            "summary_hint": "Current focus",
        },
    )

    assert merged["active_goals"] == ["Talk through relationship uncertainty"]
    assert "platypus" in merged["topics"]
    assert "family" in merged["entities"]


def test_filter_messages_for_policy_drops_stm_summary_when_not_requested():
    summary_message = type(
        "Message",
        (),
        {
            "role": "system",
            "content": "Compressed memory from earlier conversation.\nUse it only as background context.",
        },
    )()
    user_message = type(
        "Message",
        (),
        {
            "role": "user",
            "content": "Hey",
        },
    )()

    filtered = filter_messages_for_policy(
        [summary_message, user_message],
        ContextPolicy(needs_recent_history=True, needs_stm_summary=False),
    )

    assert len(filtered) == 1
    assert filtered[0].content == "Hey"


def test_identity_fact_text_detection_is_reserved_for_profile():
    assert _is_identity_fact_text("The user's name is Het.") is True
    assert _is_identity_fact_text("My name is Het.") is True
    assert _is_identity_fact_text("The user likes Taylor Swift.") is False
