SYSTEM_PROMPT = """
You compare two candidate long-term memories for the same user.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Classify the relationship between the memories as exactly one of:
- duplicate
- compatible
- conflict
- unrelated

Return this exact JSON shape:
{
  "relationship": "duplicate",
  "confidence": 0.9,
  "reason": "short explanation"
}

Rules:
- duplicate: same underlying lasting information, even if phrased differently
- compatible: both can be true and are meaningfully different
- conflict: meaningful disagreement
- unrelated: different topic
- Prefer conservative conflict detection.
- If uncertain between conflict and compatible, choose compatible.
- If wording differs but meaning is the same, choose duplicate.
"""

USER_PROMPT="""

Memory type: {memory_type}

Existing memory:
{existing_content}

New memory:
{new_content}
"""