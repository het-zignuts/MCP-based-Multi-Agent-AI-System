from __future__ import annotations

import csv
import io
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path

import fitz

from app.schemas import (
    ArtifactDocument,
    GenerationFormat,
)

MIME_TYPES: dict[GenerationFormat, str] = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}

EXTENSIONS: dict[GenerationFormat, str] = {
    "txt": ".txt",
    "md": ".md",
    "json": ".json",
    "csv": ".csv",
    "pdf": ".pdf",
}


def _clean_text(text: str) -> str:
    return (text or "").strip()


def _render_plain_text(document: ArtifactDocument) -> str:
    lines: list[str] = []
    if document.title:
        lines.append(document.title)
        lines.append("")
    if document.summary:
        lines.append(document.summary)
        lines.append("")

    for section in document.sections:
        if section.heading:
            lines.append(section.heading)
        for paragraph in section.paragraphs:
            if paragraph.strip():
                lines.append(paragraph.strip())
        for bullet in section.bullets:
            if bullet.strip():
                lines.append(f"- {bullet.strip()}")
        if section.table and section.table.headers and section.table.rows:
            lines.append(", ".join(section.table.headers))
            for row in section.table.rows:
                lines.append(", ".join(row))
        lines.append("")

    for note in document.notes:
        if note.strip():
            lines.append(f"Note: {note.strip()}")

    text = "\n".join(line.rstrip() for line in lines).strip()
    return text or json.dumps(document.model_dump(), indent=2, ensure_ascii=False)


def _render_markdown(document: ArtifactDocument) -> str:
    lines: list[str] = []
    if document.title:
        lines.append(f"# {document.title}")
        lines.append("")
    if document.summary:
        lines.append(document.summary)
        lines.append("")

    for section in document.sections:
        if section.heading:
            lines.append(f"## {section.heading}")
        for paragraph in section.paragraphs:
            if paragraph.strip():
                lines.append(paragraph.strip())
                lines.append("")
        if section.bullets:
            for bullet in section.bullets:
                if bullet.strip():
                    lines.append(f"- {bullet.strip()}")
            lines.append("")
        if section.table and section.table.headers and section.table.rows:
            lines.append("| " + " | ".join(section.table.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(section.table.headers)) + " |")
            for row in section.table.rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

    if document.notes:
        lines.append("## Notes")
        for note in document.notes:
            lines.append(f"- {note.strip()}")

    return "\n".join(line.rstrip() for line in lines).strip() or _render_plain_text(document)


def _record_keys(records: list[dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.append(key)
    return seen


def _render_csv(document: ArtifactDocument) -> str:
    records = document.records
    if not records:
        records = []
        for section in document.sections:
            for paragraph in section.paragraphs:
                records.append(
                    {
                        "section": section.heading or document.title,
                        "type": "paragraph",
                        "content": paragraph,
                    }
                )
            for bullet in section.bullets:
                records.append(
                    {
                        "section": section.heading or document.title,
                        "type": "bullet",
                        "content": bullet,
                    }
                )

    if not records:
        records = [{"title": document.title, "summary": document.summary}]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_record_keys(records))
    writer.writeheader()
    for record in records:
        writer.writerow({key: str(record.get(key, "")) for key in writer.fieldnames or []})
    return buffer.getvalue().strip()


def render_document(document: ArtifactDocument, output_format: GenerationFormat) -> str:
    if output_format == "txt":
        return _render_plain_text(document)
    if output_format == "md":
        return _render_markdown(document)
    if output_format == "json":
        return json.dumps(document.model_dump(), indent=2, ensure_ascii=False)
    if output_format == "csv":
        return _render_csv(document)
    if output_format == "pdf":
        return _render_markdown(document)
    raise ValueError(f"Unsupported format: {output_format}")


def _render_pdf_bytes(text: str) -> bytes:
    text = _clean_text(text)
    if not text:
        raise ValueError("PDF rendering failed: document contains no text.")

    pdf = fitz.open()
    page = pdf.new_page()
    margin = 36
    fontsize = 11
    line_height = fontsize * 1.2
    max_bottom = page.rect.height - margin
    fontname = "Times-Roman"
    wrap_width = 95
    current_y = margin

    for paragraph in text.splitlines():
        lines = textwrap.wrap(
            paragraph,
            width=wrap_width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        )
        if not lines:
            lines = [""]
        for line in lines:
            if current_y + line_height > max_bottom:
                page = pdf.new_page()
                current_y = margin
            page.insert_text((margin, current_y), line, fontsize=fontsize, fontname=fontname)
            current_y += line_height
        current_y += line_height

    output = pdf.tobytes()
    if not output:
        raise ValueError("PDF rendering failed: rendered bytes are empty.")
    try:
        validation_pdf = fitz.open("pdf", output)
    except Exception as exc:
        raise ValueError("PDF rendering failed: rendered bytes are invalid.") from exc
    if validation_pdf.page_count == 0:
        raise ValueError("PDF rendering failed: generated PDF has no pages.")
    return output


def render_document_bytes(document: ArtifactDocument, output_format: GenerationFormat) -> bytes:
    rendered = render_document(document, output_format)
    if output_format == "pdf":
        return _render_pdf_bytes(rendered)
    return rendered.encode("utf-8")


def preview_text_for(document: ArtifactDocument, output_format: GenerationFormat, limit: int = 2000) -> str:
    if output_format == "json":
        text = json.dumps(document.model_dump(), indent=2, ensure_ascii=False)
    else:
        text = render_document(document, output_format)
    return text[:limit]


def get_extension(output_format: GenerationFormat) -> str:
    return EXTENSIONS[output_format]


def get_mime_type(output_format: GenerationFormat) -> str:
    return MIME_TYPES[output_format]


def validate_document(document: ArtifactDocument, output_format: GenerationFormat) -> list[str]:
    warnings: list[str] = []
    if not document.title and not document.summary and not document.sections and not document.records:
        raise ValueError("Generated document is empty.")

    if output_format == "csv":
        if not document.records:
            warnings.append("CSV output was derived from sections because no explicit rows were provided.")
        else:
            keys = _record_keys(document.records)
            if not keys:
                raise ValueError("CSV output did not contain any columns.")
    return warnings


def normalize_document(document: ArtifactDocument) -> ArtifactDocument:
    normalized_sections = []
    for section in document.sections:
        normalized_sections.append(
            section.model_copy(
                update={
                    "heading": _clean_text(section.heading),
                    "paragraphs": [_clean_text(item) for item in section.paragraphs if _clean_text(item)],
                    "bullets": [_clean_text(item) for item in section.bullets if _clean_text(item)],
                }
            )
        )

    normalized_records = []
    for record in document.records:
        normalized_records.append(
            {
                str(key).strip(): str(value).strip()
                for key, value in record.items()
                if str(key).strip()
            }
        )

    return document.model_copy(
        update={
            "title": _clean_text(document.title),
            "summary": _clean_text(document.summary),
            "sections": normalized_sections,
            "records": normalized_records,
            "notes": [_clean_text(item) for item in document.notes if _clean_text(item)],
        }
    )


def filename_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def slugify(text: str, fallback: str = "generated-file") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return cleaned or fallback
