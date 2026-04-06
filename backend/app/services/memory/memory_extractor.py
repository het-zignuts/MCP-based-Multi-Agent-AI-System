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
- memory_metadata: object with small useful metadata

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
        "source": "conversation"
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
    "source": "conversation"
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
    "source": "conversation"
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
    "source": "conversation"
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
    ])

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