from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_ROOT
from app.crud.file import create_file
from app.crud.message import create_message
from app.db.models.message import Message
from app.schemas.file import FileCreate
from app.schemas.message import MessageCreate
from app.services.file_generation.intent_router import (
    GenerationDecision,
    classify_generation_intent_with_llm,
    detect_generation_intent,
    normalize_format,
)
from app.services.file_generation.models import ArtifactDocument, ArtifactRenderedFile, GenerationFormat, GenerationOutcome
from app.services.file_generation.prompt_builder import build_generation_prompt
from app.services.file_generation.serializer import filename_timestamp, get_extension, get_mime_type, normalize_document, preview_text_for, render_document_bytes, slugify, validate_document
from app.services.llm_service import get_llm_response_async
from app.services.memory.unified_memory_service import (
    UnifiedMemoryContext,
    build_unified_memory_context,
)
from app.services.rag.retriever import retrieve_pipeline


GENERATED_UPLOAD_DIR = BACKEND_ROOT / "uploads" / "generated"

GENERATION_SYSTEM_PROMPT = """
You are a document generator. Produce valid JSON only, with no markdown fences, no extra text, and no explanation.
Follow the requested schema exactly and output only the JSON object.
"""


def _ensure_output_dir() -> None:
    GENERATED_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _merge_context_segments(*segments: str) -> str:
    cleaned = [segment.strip() for segment in segments if segment and segment.strip()]
    return "\n\n---\n\n".join(cleaned)


def _extract_json_payload(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    # Remove markdown fences and surrounding explanation text.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]

    return cleaned


def _serialize_message_history(messages: list) -> str:
    lines: list[str] = []
    for message in messages:
        role = getattr(message, "role", "").capitalize()
        content = getattr(message, "content", "") or ""
        if not content.strip():
            continue

        attached_files = getattr(message, "files", []) or []
        if attached_files:
            file_lines = "\n".join(
                f"  - {getattr(file, 'filename', 'unknown')} ({getattr(file, 'status', '')})"
                for file in attached_files
            )
            content = f"{content}\nAttached files:\n{file_lines}"

        lines.append(f"{role}: {content}")

    if not lines:
        return ""

    return "Conversation history:\n" + "\n\n".join(lines)


async def _build_context(
    db: AsyncSession,
    *,
    user_id,
    conversation_id,
    prompt: str,
    file_ids: list[UUID] | None = None,
) -> tuple[str, UnifiedMemoryContext]:
    file_context = ""
    if file_ids:
        file_context = await retrieve_pipeline(
            prompt,
            file_ids,
            conversation_id,
            user_id,
            db,
        )

    unified = await build_unified_memory_context(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
        query_text=prompt,
        rag_context=file_context,
    )

    message_history_context = _serialize_message_history(unified.messages)
    context_text = _merge_context_segments(
        unified.combined_context,
        unified.stm_summary,
        message_history_context,
    )
    return context_text, unified


async def _generate_document(
    db: AsyncSession,
    *,
    user_id,
    conversation_id,
    prompt: str,
    output_format: GenerationFormat,
    file_ids: list[UUID] | None = None,
) -> tuple[ArtifactDocument, list[str], UnifiedMemoryContext]:
    context_text, unified_context = await _build_context(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        prompt=prompt,
        file_ids=file_ids,
    )

    llm_prompt = build_generation_prompt(
        user_request=prompt,
        output_format=output_format,
        context_text=context_text,
    )
    response = await get_llm_response_async(
        [{"role": "user", "content": llm_prompt}],
        purpose="file_generation",
        system_prompt=GENERATION_SYSTEM_PROMPT,
    )

    extracted = _extract_json_payload(response)
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError as exc:
        logger.warning(
            "File generation invalid JSON | original=%s | extracted=%s",
            response,
            extracted,
        )
        raise HTTPException(
            status_code=502,
            detail="The file generator returned invalid JSON.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="The file generator returned invalid JSON.",
        ) from exc

    try:
        document = ArtifactDocument.model_validate(parsed)
        document = normalize_document(document)
        warnings = validate_document(document, output_format)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return document, warnings, unified_context


def _suggest_title(prompt: str, document: ArtifactDocument) -> str:
    for candidate in (document.title, document.summary, prompt):
        cleaned = (candidate or "").strip()
        if cleaned:
            return cleaned
    return "Generated file"


def _build_filename(prompt: str, document: ArtifactDocument, output_format: GenerationFormat) -> str:
    title = _suggest_title(prompt, document)
    return f"{filename_timestamp()}_{slugify(title)}{get_extension(output_format)}"


def _build_storage_path(filename: str) -> str:
    _ensure_output_dir()
    return str(GENERATED_UPLOAD_DIR / filename)


def _build_preview_payload(
    *,
    document: ArtifactDocument,
    output_format: GenerationFormat,
    filename: str,
    warnings: list[str],
) -> dict:
    return {
        "filename": filename,
        "file_type": get_mime_type(output_format),
        "format": output_format,
        "preview_text": preview_text_for(document, output_format),
        "warnings": warnings,
    }


async def preview_file_artifact(
    db: AsyncSession,
    *,
    user_id,
    conversation_id,
    prompt: str,
    output_format: str | None,
    file_ids: list[UUID] | None = None,
    explicit_action: str | None = None,
) -> dict:
    decision = detect_generation_intent(
        text=prompt,
        explicit_format=output_format,
        explicit_action=explicit_action,
    )
    if not decision.should_generate:
        decision = await classify_generation_intent_with_llm(
            text=prompt,
            current_decision=decision,
        )

    normalized_format = normalize_format(decision.format) or "md"
    document, warnings, _ = await _generate_document(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        prompt=prompt,
        output_format=normalized_format,
        file_ids=file_ids,
    )
    filename = _build_filename(prompt, document, normalized_format)
    return {
        "decision": decision,
        "document": document.model_dump(),
        "preview": _build_preview_payload(
            document=document,
            output_format=normalized_format,
            filename=filename,
            warnings=warnings,
        ),
    }


async def generate_file_artifact(
    db: AsyncSession,
    *,
    user_id,
    conversation_id,
    prompt: str,
    output_format: str | None,
    decision: GenerationDecision,
    file_ids: list[UUID] | None = None,
    explicit_action: str | None = None,
    user_message: Message | None = None,
    persist_messages: bool = True,
) -> GenerationOutcome:
    # decision = detect_generation_intent(
    #     text=prompt,
    #     explicit_format=output_format,
    #     explicit_action=explicit_action,
    # )
    # if not decision.should_generate:
    #     decision = await classify_generation_intent_with_llm(
    #         text=prompt,
    #         current_decision=decision,
    #     )

    if not decision.should_generate:
        raise HTTPException(
            status_code=400,
            detail="The request was not recognized as a file generation request.",
        )

    normalized_format = normalize_format(decision.format) or "md"
    if persist_messages and user_message is None:
        user_message = await create_message(
            db,
            MessageCreate(
                user_id=user_id,
                conversation_id=conversation_id,
                content=prompt,
                role="user",
                token_count=None,
                file_ids=file_ids or [],
            ),
        )

    document, warnings, _ = await _generate_document(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        prompt=prompt,
        output_format=normalized_format,
        file_ids=file_ids,
    )

    rendered_bytes = render_document_bytes(document, normalized_format)
    filename = _build_filename(prompt, document, normalized_format)
    storage_path = _build_storage_path(filename)
    Path(storage_path).write_bytes(rendered_bytes)

    file_record = await create_file(
        db,
        FileCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            filename=filename,
            file_type=get_mime_type(normalized_format),
            file_size=len(rendered_bytes),
            storage_path=storage_path,
            status="processed",
        ),
    )

    assistant_message = None
    if persist_messages:
        file_preview_url = f"/files/generated/{file_record.id}/preview"
        generated_message = MessageCreate(
            user_id=user_id,
            conversation_id=conversation_id,
            content=(
                f"I generated {filename} and attached it to this conversation. "
                f"Preview the file here: "
            ),
            role="assistant",
            token_count=None,
            file_ids=[file_record.id],
        )
        assistant_message = await create_message(db, generated_message)

    preview = _build_preview_payload(
        document=document,
        output_format=normalized_format,
        filename=filename,
        warnings=warnings,
    )
    download_url = f"/files/generated/{file_record.id}/download"
    logger.info(
        "Generated file artifact | file_id={} | filename={} | format={} | warnings={}",
        file_record.id,
        filename,
        normalized_format,
        warnings,
    )

    return GenerationOutcome(
        decision=decision,
        document=document,
        rendered_file=ArtifactRenderedFile(
            filename=filename,
            storage_path=storage_path,
            mime_type=get_mime_type(normalized_format),
            extension=get_extension(normalized_format),
            file_size=len(rendered_bytes),
            preview_text=preview["preview_text"],
        ),
        file_record=file_record,
        warnings=warnings,
        stm_state={},
        download_url=download_url,
        assistant_message=assistant_message,
        user_message=user_message,
    )
