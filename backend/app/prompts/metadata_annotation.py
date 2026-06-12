SYSTEM_PROMPT = """
You classify an existing durable memory so it can be used in a structured user profile.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Return this exact JSON shape:
{
  "profile_category": "other",
  "profile_attributes": [],
  "confidence": 0.0
}

Rules:
- profile_category must be exactly one of:
  - identity
  - preference
  - project
  - relationship
  - wellbeing
  - other
- profile_attributes must be a short list of durable user attributes explicitly represented in the memory.
- Allowed profile_attributes examples: name, profession, role, company, location, education, age, identity, relationship, wellbeing.
- Use an empty list when no durable profile attribute is explicitly present.
- Only mark profile_category as identity when the memory clearly describes who the user is or a stable attribute of the user's identity.
- Prefer conservative labeling.
- Do not infer beyond the memory text itself.
- confidence must be a float between 0.0 and 1.0.
"""

USER_PROMPT = """Classify the following memory for structured profile extraction:

Memory type:
{memory_type}

Memory content:
\"\"\"
{content}
\"\"\"
"""