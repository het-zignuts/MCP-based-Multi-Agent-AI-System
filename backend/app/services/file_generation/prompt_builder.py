from __future__ import annotations

from app.services.file_generation.models import GenerationFormat


def build_generation_prompt(
    *,
    user_request: str,
    output_format: GenerationFormat,
    context_text: str,
) -> str:
    return f"""
You are a document generator. Produce a structured artifact as valid JSON only.

Use the user's request and the provided context to create a useful output in the requested format.
Do not invent facts that are not grounded in the request or context.
Do not wrap the JSON in markdown fences.

Return this schema:
{{
  "title": "string",
  "summary": "string",
  "sections": [
    {{
      "heading": "string",
      "paragraphs": ["string"],
      "bullets": ["string"],
      "table": {{
        "headers": ["string"],
        "rows": [["string"]]
      }}
    }}
  ],
  "records": [
    {{"any_key": "any value as string"}}
  ],
  "notes": ["string"]
}}

Requested output format: {output_format}

User request:
{user_request.strip()}

Context:
{context_text.strip() or "No extra context provided."}
"""

