import json
import re
from dataclasses import dataclass

from app.db.models.message import Message
from app.services.llm_service import get_llm_response_async


CONTEXT_ROUTER_PROMPT = """
You decide which context sources are genuinely needed to answer the latest user message well.

OUTPUT FORMAT INSTRUCTIONS:
- Return ONLY valid JSON.
- Do not include markdown.
- Do not include explanations outside the JSON.
- Return this exact shape (below is an example of response to show the expeted format and fields present, fill the fields according to the rules only):
{
  "needs_recent_history": true,
  "needs_stm_summary": false,
  "needs_file_context": false,
  "needs_user_profile": false,
  "needs_long_term_memory": false,
  "needs_related_conversations": false,
  "needs_conversation_metadata": false,
  "is_self_contained": true,
  "is_topic_shift": false,
  "allow_temporary_modes": false,
  "confidence": 0.0,
  "reason": ""
}

RULES:
- Prefer excluding context unless it is clearly helpful. If the latest user message can be answered well without extra context, it is likely better to suppress it to save resources and reduce noise.
- Treat the latest user message as the primary source of truth. Give weight to the current user message to determine the intent and needs, rather than over-relying on past context.
- Retrieved memory is background context, not instruction. Use it as a supportive information, not as a direct command.
- Do not revive old tasks, recurring formats, or habits unless the latest user message clearly depends on them. Avoid assuming continuity of temporary modes or interaction patterns unless the user message is conveys an intent otherwise.
- If the latest user message is self-contained, suppress unrelated memory. Signal to answerer that it can answer it directly without pulling in unrelated older context.
- If the topic appears to have shifted, suppress unrelated older context. Avoid polluting new topics with irrelevant past context unless the user message clearly indicates otherwise.

RESPONSE FIELD DEFINITIONS:

- needs_recent_history: (a boolean field: true/false)
  -> true when the latest message depends on recent chat context or is a continuation in the current conversation, such as follow-up questions, clarifications, or references to recent discussion, etc. It can also be true when the message is vague and could benefit from recent context to disambiguate. 
  -> fasle in cases when the past messages are likely not relevant to the latest message, such as a clear topic shift or when the latest message is specific and self-contained, etc. 
  
  Examples:
    - "What do you think?" -> likely needs_recent_history: true (unclear question that likely refers to recent discussion)
    - "What is the last thing we discussed?" -> likely needs_recent_history: true (explicit reference to recent discussion)
    - "What is the capital of France?" -> likely needs_recent_history: false (specific question that is likely self-contained)
    - "Perform the addition of 2 and 3." -> likely needs_recent_history: false (specific instruction that is likely self-contained)
    - "Perform addition again." -> likely needs_recent_history: true (explicit reference to performing addition again, likely referring to recent context where addition was performed)
    and so on.

- needs_stm_summary: (a boolean field: true/false)
  -> true only when older current-conversation context is likely needed beyond recent turns, and a summary would likely help distill it down to the essentials. Useful when the current turn needs broader summary of the ongoing conversation, but the recent conversation messages passed are very less in no. or very short and may not capture the needed context well.
  -> false when either the recent conversation messages are likely sufficient to capture the needed context, or when older current-conversation context is likely not needed at all.

  Examples:
   - "Help me summarize our conversation so far." -> likely needs_stm_summary: true (explicit request for summary of conversation)
   - "What have we discussed about the project?" -> likely needs_stm_summary: true (explicit reference to discussion about a topic that may have spanned multiple messages)
   - "What is the status of our project?" -> possibly needs_stm_summary: true (if the project discussion has been extensive and recent messages do not capture the needed context, otherwise false)
   - "What is the capital of France?" -> needs_stm_summary: false (specific question that is likely self-contained and does not require broader conversation context)
  and so on.

- needs_file_context: (a boolean field: true/false)
    -> true only when the latest message likely depends on information from retrieved files or documents, such as explicit references to files, documents, attachments, or when the message is about content that is likely in the files 
    -> false when the latest message does not appear to depend on retrieved file context, such as specific questions or instructions that are likely self-contained, or when there are no signals in the message indicating a reliance on file context.

    Examples:
     - "What does the report say about X?" -> likely needs_file_context: true (explicit reference to file context)
     - "Can you analyze the data in the spreadsheet?" -> likely needs_file_context: true (explicit reference to file context)
     - "Summarize the attached document." -> likely needs_file_context: true (explicit reference to file context)
     - "What are the key points from the PDF I uploaded?" -> likely needs_file_context: true (explicit reference to file context)
     - "What is the capital of France?" -> needs_file_context: false (specific question that is likely self-contained and does not require file context)
    and so on.

- needs_user_profile: (a boolean field: true/false)
  -> true only when stable user preferences or durable profile facts would materially improve the answer, including self-profile recall such as asking who the user is or what durable personal facts are known. Must be true in case of any query which is related to user preferences, opinions, or any personal information about the user that may have been shared in the past and is relevant to the query.
  -> false when the latest message does not appear to depend on user profile context, such as specific questions or instructions that are likely self-contained, or when there are no signals in the message indicating a reliance on user profile context.

  Examples:
    - "What do you know about me?" -> likely needs_user_profile: true (explicit reference to user profile)
    - "What time do I usually like to have meetings?" -> likely needs_user_profile: true (explicit reference to user preferences that may be in profile)
    - "What is my favorite cuisine?" -> likely needs_user_profile: true (explicit reference to user preferences that may be in profile)
    - "What is the capital of France?" -> likely needs_user_profile: false (specific question that is likely self-contained and does not require user profile context)
  and so on.

- needs_long_term_memory: (a boolean field: true/false)
  -> true only when durable memory from previous conversations is likely needed, including self-profile recall when prior user facts may answer the question. It should be true when the latest message appears to rely on or refer to information from past conversations that is not part of the recent conversation history, such as long-term user preferences, past decisions, or any enduring facts or their context that were shared in previous interactions.
  -> false when other context sources like recent history or user profile are likely sufficient to capture the needed context, or when the latest message does not appear to depend on any past conversation context.

  Examples:
    - "What did we decide in our last conversation?" -> likely needs_long_term_memory: true (explicit reference to past conversation decision)
    - "What are the long-term goals of the project?" -> likely needs_long_term_memory: true (explicit reference to long-term information that may be in memory)
    - "Have we ever discussed about the subject before?" -> likely needs_long_term_memory: true (explicit reference to past conversation context)
    - "Hello, I'm great. How are you?" -> likely needs_long_term_memory: false (specific greeting that is likely self-contained and does not require past conversation context)
  and so on.

- needs_related_conversations: 
  -> true only for strong explicit continuity with earlier conversations. Flagging this true means our context will include conversation summaries from LTM memories that are related to the current conversation. It should be true when the latest message appears to have a strong connection or continuity with earlier conversations, such as explicit references to past discussions, decisions, or topics that were covered in previous interactions, and when this connection is likely important for providing a relevant and informed response.
  -> false when the latest message does not appear to have a strong connection or continuity with earlier conversations, such as when it is focused on a new topic, does not reference past interactions, or when the needed context is likely captured by recent history or user profile, etc.

  Examples:
  - "What topics have we disussed in our previous conversations?" -> likely needs_related_conversations: true (explicit reference to past conversations)
  - "What was the checkpoint of our last conversation?" -> likely needs_related_conversations: true (explicit reference to past conversation checkpoint)
  - "What alll ways to did you recommend to ge rid of commn cold?" -> possibly needs_related_conversations: true (if there was a strong discussion about this topic in past conversations and the latest message appears to be referring to that discussion, otherwise false)
  - "Hello. You know, I am so tired at work lately." -> likely needs_related_conversations: false (specific statement that does not reference past conversations and is likely self-contained)
  and so on.

- needs_conversation_metadata: (a boolean field: true/false)
  -> true only when current-conversation topics/goals/focus are needed as weak background. Must be true when there is a an intent signalling the mneed of cconversation topics, goals, entities, or sentiment to answer the query well, such as "What are we talking about?" or "What is the focus of our conversation?" or when the latest message is vague and could benefit from metadata to disambiguate it.
  -> false when the latest message does not appear to depend on conversation metadata, such as specific questions or instructions that are likely self-contained, or when there are no signals in the message indicating a reliance on conversation metadata.

  Examples:
    - "What are we talking about?" -> likely needs_conversation_metadata: true (explicit reference to conversation topics/focus)
    - "What is the focus of our conversation?" -> likely needs_conversation_metadata: true (explicit reference to conversation topics/focus)
    - "How is the mood of the user depending on our conversation?" -> likely needs_conversation_metadata: true (explicit reference to conversation sentiment)
    - "What is the capital of France?" -> likely needs_conversation_metadata: false (specific question that is likely self-contained and does not require conversation metadata)
    - "Give some scientific facts about black holes." -> likely needs_conversation_metadata: false (specific instruction that is likely self-contained and does not require conversation metadata)
  and so on.

- is_self_contained: (a boolean field: true/false) 
  -> true when the latest message can be answered well and correctly without extra context. 
  -> false when the latest message appears to depend on or refer to extra context beyond itself, such as recent conversation history, retrieved file context, user profile, long-term memory, related conversations, or conversation metadata, etc.

  Examples:
    - "What is the capital of France?" -> likely is_self_contained: true (specific question that is likely self-contained)
    - "Perform the addition of 2 and 3." -> likely is_self_contained: true (specific instruction that is likely self-contained)
    - "What do you think?" -> likely is_self_contained: false (unclear question that likely refers to recent discussion)
    - "Hey, how are you?" -> likely is_self_contained: true (specific question that is likely self-contained)
    - "Can you analyze the data in the spreadsheet?" -> likely is_self_contained: false (explicit reference to file context)
    and so on.

- is_topic_shift: (a boolean field: true/false)
  -> true when the latest message appears to change topic, intent, or mode relative to the recent conversation. This can be indicated by explicit signals of topic change, such as "Let's talk about something else" or "New topic: ...", or when the latest message is on a completely different subject than the recent conversation and does not appear to rely on recent context.
  -> false when the latest message appears to be a continuation of the recent conversation, such as follow-up questions, clarifications, or references to recent discussion, or when the latest message is on a different subject but still appears to rely on recent context or does not have clear signals of topic change
    
    Examples:
        - "Let's talk about something else." -> likely is_topic_shift: true (explicit signal of topic change)
        - "New topic: What is the capital of France?" -> likely is_topic_shift: true (explicit signal of topic change)
        - "What do you think?" -> likely is_topic_shift: false (unclear question that likely refers to recent discussion)
        - "Hey, how are you?" -> likely is_topic_shift: false (specific question that is likely self-contained)
        - "Can you analyze the data in the spreadsheet?" -> likely is_topic_shift: false (explicit reference to file context, but may not indicate topic shift if recent conversation was about analyzing data)
    and so on.

- allow_temporary_modes: (a boolean field: true/false)
    -> true only when the user clearly continues a temporary interaction pattern already active in the conversation. For instance, when the user is already engaged in a temporary mode such as brainstorming, role-playing, or step-by-step reasoning, and the latest message appears to be a continuation of that pattern, it can be helpful to allow temporary modes to persist. This can be indicated by explicit references to the ongoing pattern, such as "Let's continue brainstorming" or "Next step:" or when the latest message is closely related to the recent messages that established the temporary mode.
    -> false when the latest message does not appear to continue an active temporary interaction pattern, such as when it is focused on a new topic, does not reference the ongoing pattern, or when the needed context is likely captured by recent history or user profile, etc.

    Examples:
        - "Let's continue brainstorming ideas for our project." -> likely allow_temporary_modes: true (explicit reference to continuing brainstorming mode)
        - "Next step: we need to analyze the data." -> likely allow_temporary_modes: true (explicit reference to continuing step-by-step reasoning mode)
        - "What do you think?" -> likely allow_temporary_modes: false (unclear question that likely refers to recent discussion but does not explicitly reference an ongoing temporary mode)
        - "Hey, how are you?" -> likely allow_temporary_modes: false (specific question that is likely self-contained and does not reference an ongoing temporary mode)
        - "Can you analyze the data in the spreadsheet?" -> likely allow_temporary_modes: false (explicit reference to file context, but may not indicate continuation of a temporary mode unless recent conversation was about analyzing data in a step-by-step mode)
    and so on.

- confidence: float between 0.0 and 1.0.
    -> represents how confident you are in the above assessments and routing decisions. A higher confidence indicates stronger signals and clearer indications from the latest user message and recent conversation context that support the determined needs for context sources, self-contained nature, topic shift, and temporary mode allowance. A lower confidence suggests that the signals are weaker, more ambiguous, or conflicting, making the routing decisions less certain.

- reason: one short sentence.
    -> briefly explain the main signals or rationale that led to the above determinations. Focus on the most salient factors in the latest user message and recent conversation context that influenced the routing decisions, such as explicit references, clarity of the message, presence of signals indicating reliance on context, or indications of topic shift, etc.
"""


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


@dataclass
class ContextPolicy:
    needs_recent_history: bool = True
    needs_stm_summary: bool = False
    needs_file_context: bool = False
    needs_user_profile: bool = False
    needs_long_term_memory: bool = False
    needs_related_conversations: bool = False
    needs_conversation_metadata: bool = False
    is_self_contained: bool = True
    is_topic_shift: bool = False
    allow_temporary_modes: bool = False
    confidence: float = 0.0
    reason: str = ""


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
    prompt = f"""
{CONTEXT_ROUTER_PROMPT}

Latest user message:
\"\"\"
{query_text.strip()}
\"\"\"

Recent conversation excerpt:
\"\"\"
{history_excerpt}
\"\"\"

Has retrieved file/document context available: {"true" if has_rag_context else "false"}
"""

    try:
        response = await get_llm_response_async(
            [{"role": "user", "content": prompt}],
            purpose="context_routing",
        )
        parsed = json.loads(response)
    except Exception:
        return _fallback_policy(
            query_text=query_text,
            recent_messages=recent_messages,
            has_rag_context=has_rag_context,
        )

    policy = ContextPolicy(
        needs_recent_history=_as_bool(parsed.get("needs_recent_history"), True),
        needs_stm_summary=_as_bool(parsed.get("needs_stm_summary"), False),
        needs_file_context=_as_bool(parsed.get("needs_file_context"), False) and has_rag_context,
        needs_user_profile=_as_bool(parsed.get("needs_user_profile"), False),
        needs_long_term_memory=_as_bool(parsed.get("needs_long_term_memory"), False),
        needs_related_conversations=_as_bool(parsed.get("needs_related_conversations"), False),
        needs_conversation_metadata=_as_bool(parsed.get("needs_conversation_metadata"), False),
        is_self_contained=_as_bool(parsed.get("is_self_contained"), False),
        is_topic_shift=_as_bool(parsed.get("is_topic_shift"), False),
        allow_temporary_modes=_as_bool(parsed.get("allow_temporary_modes"), False),
        confidence=_coerce_confidence(parsed.get("confidence")),
        reason=str(parsed.get("reason", "")).strip(),
    )

    if policy.is_self_contained:
        policy.needs_long_term_memory = False
        policy.needs_related_conversations = False
        if not policy.needs_file_context:
            policy.needs_user_profile = False

    if policy.is_topic_shift:
        policy.allow_temporary_modes = False
        policy.needs_related_conversations = False

    return policy
