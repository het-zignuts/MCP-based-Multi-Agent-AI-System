import json
from typing import Any

from app.services.llm_service import get_llm_response_async


MEMORY_EXTRACTION_PROMPT = """
You extract durable long-term memory candidates from a conversation.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Extract only information that is likely to remain useful later.

Allowed memory types:
- preference
- fact
- decision
- task

For each extracted memory, return:
- content: concise standalone sentence
- memory_type: one of the allowed types
- importance_score: float between 0.0 and 1.0
- confidence_score: float between 0.0 and 1.0
- evidence: one of:
  - explicit
  - repeated
  - inferred
- temporal_scope: one of:
  - durable
  - ongoing
  - temporary
- memory_metadata: object with small useful metadata including:
  - source: "conversation"
  - specificity_score: float between 0.0 and 1.0
  - support_span_count: integer >= 0
  - is_generic_persona_claim: boolean
  - has_concrete_anchor: boolean
  - source_kind: one of "statement", "question", "request", "assistant_claim", "hypothetical", "unclear"
  - profile_write_eligible: boolean
  - profile_write_confidence: float between 0.0 and 1.0
  - value_specificity: one of "concrete", "vague"
  - overwrite_risk: one of "none", "low", "high"
  - profile_category: one of "identity", "preference", "project", "relationship", "wellbeing", "other"
  - profile_attributes: short list of durable user attributes when applicable, else []

Return this JSON shape exactly:
{
  "memories": [
    {
      "content": "...",
      "memory_type": "preference",
      "importance_score": 0.8,
      "confidence_score": 0.9,
      "evidence": "explicit",
      "temporal_scope": "durable",
      "memory_metadata": {
        "source": "conversation",
        "specificity_score": 0.9,
        "support_span_count": 1,
        "is_generic_persona_claim": false,
        "has_concrete_anchor": true,
        "profile_category": "preference",
        "profile_attributes": []
      }
    }
  ]
}

Rules:
- Prefer durable user-specific information that is likely to remain useful in future conversations.
- Preserve important project context, explicit preferences, stable facts, decisions, and ongoing tasks.
- Do NOT store short-lived discussion topics unless they clearly indicate a durable preference, stable fact, or ongoing responsibility.
- Do NOT store statements that only describe what the user is currently asking about unless they also reveal lasting personal context.
- A directly stated personal preference, fact, decision, or ongoing task may be stored.
- A one-off topic of discussion is not automatically a durable memory.
- Broad inferred persona summaries should be avoided unless they are both highly specific and clearly supported across the conversation.
- Prefer concrete anchored memories over vague identity/personality claims.
- A memory is "generic persona" when it mainly describes broad traits or tastes without a concrete recurring anchor, named entity, project, decision, or responsibility.
- specificity_score should be high only when the memory is concrete and narrow rather than broad and generic.
- support_span_count should estimate how many distinct parts of the conversation support the memory.
- has_concrete_anchor should be true when the memory is tied to a named entity, project, recurring behavior, explicit preference, or durable responsibility.
- profile_category should describe the memory's role in the user's profile rather than its memory_type.
- profile_attributes should list durable user attributes explicitly captured by the memory, such as name, profession, role, company, location, education, or identity labels, and should be empty when not applicable.
- source_kind should describe where the memory really comes from. If the content comes only from an assistant answer or a user recall-question, do not mark it as a user statement.
- profile_write_eligible should be true only when the memory is safe to use later for profile refresh or overwrite decisions.
- profile_write_confidence should reflect confidence in that profile-write decision.
- value_specificity should be "concrete" only when the value is specific enough to be actionable later.
- overwrite_risk should be "high" when this memory might wrongly replace a stronger stored fact.
- Use "explicit" when the user directly stated the information.
- Use "repeated" when the information appears multiple times or is strongly reinforced across the conversation.
- Use "inferred" only when the conclusion is reasonable but not directly stated.
- Use "durable" for stable long-term information.
- Use "ongoing" for projects, responsibilities, or tasks that are still active.
- Use "temporary" for short-lived or one-off discussion context.
- If confidence is low, do not include the memory.
- If nothing is worth storing, return {"memories": []}.
- Do not invent facts.

Examples:

Example 1
Conversation:
user: I prefer concise answers.
Output memory:
{
  "content": "The user prefers concise answers.",
  "memory_type": "preference",
  "importance_score": 0.9,
  "confidence_score": 0.95,
  "evidence": "explicit",
  "temporal_scope": "durable",
  "memory_metadata": {
    "source": "conversation",
    "specificity_score": 0.95,
    "support_span_count": 1,
    "is_generic_persona_claim": false,
    "has_concrete_anchor": true,
    "profile_category": "preference",
    "profile_attributes": []
  }
}

Example 2
Conversation:
user: I am currently building a chatbot with pgvector.
Output memory:
{
  "content": "The user is building a chatbot with pgvector.",
  "memory_type": "task",
  "importance_score": 0.85,
  "confidence_score": 0.95,
  "evidence": "explicit",
  "temporal_scope": "ongoing",
  "memory_metadata": {
    "source": "conversation",
    "specificity_score": 0.9,
    "support_span_count": 1,
    "is_generic_persona_claim": false,
    "has_concrete_anchor": true,
    "profile_category": "project",
    "profile_attributes": []
  }
}

Example 3
Conversation:
user: Can we talk about this poem?
Output:
No memory should be stored unless the conversation also shows that this reflects a durable preference, stable fact, or ongoing goal.

Example 4
Conversation:
user: I really like Taylor Swift.
Output memory:
{
  "content": "The user likes Taylor Swift.",
  "memory_type": "preference",
  "importance_score": 0.75,
  "confidence_score": 0.9,
  "evidence": "explicit",
  "temporal_scope": "durable",
  "memory_metadata": {
    "source": "conversation",
    "profile_category": "preference",
    "profile_attributes": []
  }
}

Example 5
Conversation:
user: Let's analyze this one passage.
Output:
No memory should be stored if this is only a one-off discussion topic with no lasting user relevance.
"""

async def extract_memories_from_text(conversation_text: str) -> list[dict[str, Any]]:
    prompt = f"""
{MEMORY_EXTRACTION_PROMPT}

Conversation:
\"\"\"
{conversation_text}
\"\"\"
"""

    response = await get_llm_response_async([
        {"role": "user", "content": prompt}
    ], purpose="memory_extraction")

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return []

    memories = parsed.get("memories", [])
    if not isinstance(memories, list):
        return []

    cleaned_memories = []
    allowed_types = {"preference", "fact", "decision", "task"}
    allowed_evidence = {"explicit", "repeated", "inferred"}
    allowed_temporal_scope = {"durable", "ongoing", "temporary"}

    for item in memories:
        if not isinstance(item, dict):
            continue

        content = str(item.get("content", "")).strip()
        memory_type = str(item.get("memory_type", "")).strip()
        importance_score = item.get("importance_score", 0.5)
        confidence_score = item.get("confidence_score", 0.5)
        evidence = str(item.get("evidence", "inferred")).strip().lower()
        temporal_scope = str(item.get("temporal_scope", "temporary")).strip().lower()
        memory_metadata = item.get("memory_metadata", {})

        if not content:
            continue
        if memory_type not in allowed_types:
            continue
        if evidence not in allowed_evidence:
            evidence = "inferred"
        if temporal_scope not in allowed_temporal_scope:
            temporal_scope = "temporary"

        try:
            importance_score = float(importance_score)
        except (TypeError, ValueError):
            importance_score = 0.5

        try:
            confidence_score = float(confidence_score)
        except (TypeError, ValueError):
            confidence_score = 0.5

        importance_score = max(0.0, min(1.0, importance_score))
        confidence_score = max(0.0, min(1.0, confidence_score))

        if not isinstance(memory_metadata, dict):
            memory_metadata = {}

        specificity_score = memory_metadata.get("specificity_score", 0.5)
        support_span_count = memory_metadata.get("support_span_count", 0)
        is_generic_persona_claim = bool(memory_metadata.get("is_generic_persona_claim", False))
        has_concrete_anchor = bool(memory_metadata.get("has_concrete_anchor", False))
        source_kind = str(memory_metadata.get("source_kind", "unclear")).strip().lower()
        profile_write_eligible = bool(memory_metadata.get("profile_write_eligible", False))
        profile_write_confidence = memory_metadata.get("profile_write_confidence", confidence_score)
        value_specificity = str(memory_metadata.get("value_specificity", "vague")).strip().lower()
        overwrite_risk = str(memory_metadata.get("overwrite_risk", "high")).strip().lower()
        profile_category = str(memory_metadata.get("profile_category", "other")).strip().lower()
        profile_attributes = memory_metadata.get("profile_attributes", [])

        try:
            specificity_score = float(specificity_score)
        except (TypeError, ValueError):
            specificity_score = 0.5

        try:
            support_span_count = int(support_span_count)
        except (TypeError, ValueError):
            support_span_count = 0

        try:
            profile_write_confidence = float(profile_write_confidence)
        except (TypeError, ValueError):
            profile_write_confidence = confidence_score

        specificity_score = max(0.0, min(1.0, specificity_score))
        support_span_count = max(0, support_span_count)
        profile_write_confidence = max(0.0, min(1.0, profile_write_confidence))
        allowed_source_kinds = {
            "statement",
            "question",
            "request",
            "assistant_claim",
            "hypothetical",
            "unclear",
        }
        if source_kind not in allowed_source_kinds:
            source_kind = "unclear"
        if value_specificity not in {"concrete", "vague"}:
            value_specificity = "vague"
        if overwrite_risk not in {"none", "low", "high"}:
            overwrite_risk = "high"
        allowed_profile_categories = {
            "identity",
            "preference",
            "project",
            "relationship",
            "wellbeing",
            "other",
        }
        if profile_category not in allowed_profile_categories:
            profile_category = "other"
        if not isinstance(profile_attributes, list):
            profile_attributes = []
        profile_attributes = [
            str(attribute).strip().lower()
            for attribute in profile_attributes
            if str(attribute).strip()
        ][:5]

        memory_metadata = {
            **memory_metadata,
            "specificity_score": specificity_score,
            "support_span_count": support_span_count,
            "is_generic_persona_claim": is_generic_persona_claim,
            "has_concrete_anchor": has_concrete_anchor,
            "source_kind": source_kind,
            "profile_write_eligible": profile_write_eligible,
            "profile_write_confidence": profile_write_confidence,
            "value_specificity": value_specificity,
            "overwrite_risk": overwrite_risk,
            "profile_category": profile_category,
            "profile_attributes": profile_attributes,
        }

        cleaned_memories.append({
            "content": content,
            "memory_type": memory_type,
            "importance_score": importance_score,
            "confidence_score": confidence_score,
            "evidence": evidence,
            "temporal_scope": temporal_scope,
            "memory_metadata": memory_metadata,
        })

    return cleaned_memories
