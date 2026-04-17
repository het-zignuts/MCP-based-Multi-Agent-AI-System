import re

from loguru import logger

from app.services.llm_service import get_llm_response_async


SUMMARY_SECTION_HEADERS = [
    "1. User goals and preferences",
    "2. Constraints and important facts",
    "3. Decisions made",
    "4. Open questions and pending tasks",
    "5. Chronology and active context",
]


async def summarize_messages(messages, existing_summary: str = ""):
    text = "\n".join([f"{m.role}: {m.content}" for m in messages])
    existing_summary_block = existing_summary.strip()
    if not existing_summary_block:
        existing_summary_block = "No previous summary."

    prompt = f"""
    You are maintaining a rolling short-term memory summary for future chat turns.
    Merge the existing summary with the newly dropped conversation messages below.

    Return a compact but information-dense summary using exactly these sections:
    1. User goals and preferences
    2. Constraints and important facts
    3. Decisions made
    4. Open questions and pending tasks
    5. Chronology and active context

    Do not invent facts.
    Do not omit rules or constraints that are still active.
    Remove stale details that are clearly no longer relevant.
    Prefer durable facts over conversational filler.
    If a section has nothing meaningful, write "None".
    Keep the total summary concise enough to reuse in later prompts.

    Existing summary:
    {existing_summary_block}

    Newly dropped conversation to merge:

    {text}
    """
    summary = await get_llm_response_async([
        {"role": "user", "content": prompt}
    ], purpose="stm_summarization")
    return summary


def _normalize_header(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"^\d+[\).\s-]*", "", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def normalize_summary(summary: str) -> str:
    if not summary or not summary.strip():
        return ""

    lines = [line.rstrip() for line in summary.strip().splitlines()]
    sections = {header: [] for header in SUMMARY_SECTION_HEADERS}
    current_header = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        matched_header = next(
            (
                header
                for header in SUMMARY_SECTION_HEADERS
                if _normalize_header(line) == _normalize_header(header)
            ),
            None,
        )

        if matched_header is not None:
            current_header = matched_header
            continue

        if current_header is None:
            current_header = SUMMARY_SECTION_HEADERS[0]

        sections[current_header].append(line)

    normalized_sections = []
    for header in SUMMARY_SECTION_HEADERS:
        section_lines = sections[header]
        if not section_lines:
            section_lines = ["None"]
        normalized_sections.append(f"{header}\n" + "\n".join(section_lines))

    normalized_summary = "\n\n".join(normalized_sections).strip()
    return normalized_summary


def is_valid_summary(summary: str) -> bool:
    normalized_summary = normalize_summary(summary)
    if not normalized_summary:
        return False

    has_meaningful_content = any(
        f"{header}\nNone" not in normalized_summary
        for header in SUMMARY_SECTION_HEADERS
    )
    if not has_meaningful_content:
        logger.warning("Summary rejected | reason=no_meaningful_content")
        return False

    return all(header in normalized_summary for header in SUMMARY_SECTION_HEADERS)
