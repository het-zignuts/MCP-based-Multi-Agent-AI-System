from __future__ import annotations

import json
import re

from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm import llm
from app.schemas import GenerationDecision, GenerationFormat
from app.prompts import INTENT_CLASSIFICATION_SYSTEM_PROMPT, INTENT_CLASSIFICATION_USER_PROMPT


class _LLMGenerationDecision(BaseModel):
    """Minimal schema used only to parse the LLM's raw JSON response.

    Intentionally excludes `source` (an internal field the LLM knows nothing
    about) and clamps `confidence` to [0, 1] so out-of-range values from the
    LLM don't cause a Pydantic validation error.
    """
    should_generate: bool
    format: GenerationFormat | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = ""

    model_config = {"extra": "ignore"}  # silently drop any unexpected keys

FORMAT_ALIASES: dict[str, GenerationFormat] = {
    "txt": "txt",
    "text": "txt",
    "plain text": "txt",
    "markdown": "md",
    "md": "md",
    "json": "json",
    "csv": "csv",
    "pdf": "pdf",
}

GENERATION_KEYWORDS = (
    "generate",
    "create",
    "make",
    "export",
    "download",
    "save as",
    "write",
    "convert",
    "turn into",
    "format as",
    "produce",
)

ARTIFACT_KEYWORDS = (
    "file",
    "document",
    "report",
    "summary",
    "brief",
    "spec",
    "notes",
)


def normalize_format(value: str | None) -> GenerationFormat | None:
    if not value:
        return None

    normalized = value.strip().lower()
    if normalized in FORMAT_ALIASES:
        return FORMAT_ALIASES[normalized]
    if normalized.endswith(".txt"):
        return "txt"
    if normalized.endswith(".md"):
        return "md"
    if normalized.endswith(".json"):
        return "json"
    if normalized.endswith(".csv"):
        return "csv"
    if normalized.endswith(".pdf"):
        return "pdf"
    return None


def _keyword_score(text: str) -> tuple[bool, bool]:
    normalized_text = re.sub(r"\s+", " ", (text or "").lower()).strip()
    lowered = f" {normalized_text} "
    has_generation = any(f" {keyword} " in lowered for keyword in GENERATION_KEYWORDS)
    has_artifact = any(f" {keyword} " in lowered for keyword in ARTIFACT_KEYWORDS)
    return has_generation, has_artifact


def _format_from_text(text: str) -> GenerationFormat | None:
    lowered = (text or "").lower()
    for keyword, fmt in FORMAT_ALIASES.items():
        if f" {keyword} " in f" {lowered} ":
            return fmt
    return None


def detect_generation_intent(
    *,
    text: str,
    explicit_format: str | None = None,
    explicit_action: str | None = None,
) -> GenerationDecision:
    requested_format = normalize_format(explicit_format) or _format_from_text(text)
    if explicit_action and explicit_action.strip().lower() in {"generate", "generate_file", "preview"}:
        should_generate = explicit_action.strip().lower() != "chat"
        return GenerationDecision(
            should_generate=should_generate,
            format=requested_format or "md",
            confidence=1.0,
            reason="Explicit UI action requested artifact generation.",
            source="ui",
        )

    has_generation, has_artifact = _keyword_score(text)
    if requested_format and has_generation:
        return GenerationDecision(
            should_generate=True,
            format=requested_format,
            confidence=0.95,
            reason="User explicitly asked for a file and named the format.",
            source="heuristic",
        )

    if has_generation and has_artifact:
        return GenerationDecision(
            should_generate=True,
            format=requested_format or "md",
            confidence=0.8,
            reason="User language strongly suggests a file artifact.",
            source="heuristic",
        )

    if requested_format and ("download" in text.lower() or "save" in text.lower() or "export" in text.lower()):
        return GenerationDecision(
            should_generate=True,
            format=requested_format,
            confidence=0.78,
            reason="Format was named and the request implies export or download.",
            source="heuristic",
        )

    return GenerationDecision(
        should_generate=False,
        format=requested_format,
        confidence=0.25,
        reason="No strong artifact intent detected.",
        source="heuristic",
    )


# def _extract_json_payload(text: str) -> str:
#     cleaned = (text or "").strip()
#     if not cleaned:
#         return ""

#     cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
#     cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()

#     if cleaned.startswith("{") and cleaned.endswith("}"):
#         return cleaned

#     start = cleaned.find("{")
#     end = cleaned.rfind("}")
#     if start != -1 and end != -1 and end > start:
#         return cleaned[start : end + 1]

#     return cleaned


async def classify_generation_intent_with_llm(
    *,
    text: str,
    current_decision: GenerationDecision,
) -> GenerationDecision:
    user_prompt = INTENT_CLASSIFICATION_USER_PROMPT.format(user_message=text, heuristic_result=current_decision.model_dump())

    try:
        messages = [
            {"role": "system", "content": INTENT_CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        # Parse against the LLM-only schema first to avoid validation errors
        # caused by missing/unexpected fields (e.g. `source`, bad `confidence`).
        raw = await llm.structured(
            messages,
            purpose="file_generation_intent",
            response_model=_LLMGenerationDecision,
        )
        decision = GenerationDecision(
            should_generate=raw.should_generate,
            format=raw.format,
            confidence=raw.confidence,
            reason=raw.reason,
            source="llm",
        )
        logger.info(
            "File generation intent LLM decision | should_generate={} | format={} | confidence={} | reason={}",
            decision.should_generate,
            decision.format,
            decision.confidence,
            decision.reason,
        )
    except Exception:
        logger.exception("File generation intent parser failed, falling back to heuristic decision.")
        return current_decision

    return decision
