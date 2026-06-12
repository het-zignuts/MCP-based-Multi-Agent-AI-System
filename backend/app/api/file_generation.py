from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.file_generation import (
    FileGenerationPreviewResponse,
    FileGenerationRequest,
    FileGenerationResultResponse,
    GeneratedFileRead,
)
from app.services.file_generation.file_renderer import get_mime_type
from app.services.file_generation.file_generation_service import (
    generate_file_artifact,
    # preview_file_artifact,
)
from app.crud.file import get_file

router = APIRouter(prefix="/files", tags=["File Generation"])


# @router.post("/generate/preview", response_model=FileGenerationPreviewResponse)
# async def preview_generation(
#     payload: FileGenerationRequest,
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await preview_file_artifact(
#         db,
#         user_id=payload.user_id,
#         conversation_id=payload.conversation_id,
#         prompt=payload.prompt,
#         output_format=payload.output_format,
#         file_ids=payload.file_ids,
#         explicit_action=payload.explicit_action,
#     )
#     decision = result["decision"]
#     return {
#         "decision": {
#             "should_generate": decision.should_generate,
#             "format": decision.format,
#             "confidence": decision.confidence,
#             "reason": decision.reason,
#             "source": decision.source,
#         },
#         "document": result["document"],
#         "preview": result["preview"],
#     }


# @router.post("/generate", response_model=FileGenerationResultResponse)
# async def generate(
#     payload: FileGenerationRequest,
#     db: AsyncSession = Depends(get_db),
# ):
#     outcome = await generate_file_artifact(
#         db,
#         user_id=payload.user_id,
#         conversation_id=payload.conversation_id,
#         prompt=payload.prompt,
#         output_format=payload.output_format,
#         file_ids=payload.file_ids,
#         explicit_action=payload.explicit_action,
#     )

#     if outcome.rendered_file is None:
#         raise HTTPException(status_code=500, detail="Generated file metadata is missing.")
#     if outcome.file_record is None:
#         raise HTTPException(status_code=500, detail="Generated file record is missing.")

#     file_read = GeneratedFileRead.model_validate(outcome.file_record)
#     return {
#         "decision": {
#             "should_generate": outcome.decision.should_generate,
#             "format": outcome.decision.format,
#             "confidence": outcome.decision.confidence,
#             "reason": outcome.decision.reason,
#             "source": outcome.decision.source,
#         },
#         "preview": {
#             "filename": outcome.rendered_file.filename,
#             "file_type": outcome.rendered_file.mime_type,
#             "format": outcome.decision.format,
#             "preview_text": outcome.rendered_file.preview_text,
#             "warnings": outcome.warnings,
#         },
#         "download_url": outcome.download_url,
#         "file": file_read.model_dump(),
#         "assistant_message_id": getattr(outcome.assistant_message, "id", None),
#     }


@router.get("/generated/{file_id}/download")
async def download_generated_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    file_record = await get_file(db, file_id)
    path = Path(file_record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generated file is missing from storage.")

    mime_type = file_record.file_type or get_mime_type(_infer_format_from_path(path))
    return FileResponse(
        path,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.filename}"',
        },
    )


@router.get("/generated/{file_id}/raw")
async def raw_generated_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    file_record = await get_file(db, file_id)
    path = Path(file_record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generated file is missing from storage.")

    mime_type = file_record.file_type or get_mime_type(_infer_format_from_path(path))
    headers = {}
    if mime_type == "application/pdf":
        headers["Content-Disposition"] = f'inline; filename="{file_record.filename}"'

    return FileResponse(
        path,
        media_type=mime_type,
        headers=headers or None,
    )


@router.get("/generated/{file_id}/preview", response_class=HTMLResponse)
async def preview_generated_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    file_record = await get_file(db, file_id)
    path = Path(file_record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generated file is missing from storage.")

    mime_type = file_record.file_type.split(";")[0].strip().lower()
    raw_content = None
    if mime_type == "application/pdf":
        preview_body = f"""
            <iframe
              src=\"/files/generated/{file_id}/raw\"
              width=\"100%\"
              height=\"100%\"
              style=\"border:none; background: #0f172a;\"
            ></iframe>
        """
    else:
        raw_content = path.read_text(encoding="utf-8", errors="replace")
        if mime_type == "text/csv":
            rows = []
            try:
                for row in csv.reader(raw_content.splitlines()):
                    rows.append([html.escape(cell) for cell in row])
            except Exception:
                rows = []

            if rows:
                table_rows = [
                    "<table style=\"width:100%; border-collapse: collapse;\">",
                    "<thead><tr>"
                    + "".join(
                        f'<th style=\"border:1px solid #334155; padding:0.5rem; text-align:left;\">{cell}</th>'
                        for cell in rows[0]
                    )
                    + "</tr></thead>",
                    "<tbody>",
                ]
                for row in rows[1:]:
                    table_rows.append(
                        "<tr>"
                        + "".join(
                            f'<td style=\"border:1px solid #334155; padding:0.5rem;\">{cell}</td>'
                            for cell in row
                        )
                        + "</tr>"
                    )
                table_rows.append("</tbody>")
                table_rows.append("</table>")
                preview_body = "\n".join(table_rows)
            else:
                preview_body = f"""
                    <pre id=\"preview-text\" style=\"white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;\">{html.escape(raw_content)}</pre>
                """
        elif mime_type == "application/json":
            try:
                parsed_json = json.loads(raw_content)
                pretty = json.dumps(parsed_json, indent=2, ensure_ascii=False)
            except Exception:
                pretty = raw_content
            preview_body = f"""
                <pre id=\"preview-text\" style=\"white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;\">{html.escape(pretty)}</pre>
            """
        else:
            preview_body = f"""
                <pre id=\"preview-text\" style=\"white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;\">{html.escape(raw_content)}</pre>
            """

    page_html = f"""
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
          <title>Preview - {file_record.filename}</title>
          <style>
            body {{ margin: 0; font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }}
            .toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1rem; background: #111827; flex-wrap: wrap; }}
            .toolbar button, .toolbar a {{ color: #fff; background: #1d4ed8; border: none; border-radius: 0.5rem; padding: 0.6rem 1rem; cursor: pointer; text-decoration: none; }}
            .toolbar button:hover, .toolbar a:hover {{ background: #2563eb; }}
            .preview-container {{ padding: 1rem; height: calc(100vh - 88px); overflow: auto; }}
            .preview-title {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #334155; padding: 0.75rem; text-align: left; }}
            th {{ background: #1e293b; }}
            pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
          </style>
        </head>
        <body>
          <div class=\"toolbar\">
            <div>
              <div class=\"preview-title\">Preview: {file_record.filename}</div>
              <div>{file_record.file_type}</div>
            </div>
            <div style=\"display:flex; gap: 0.75rem; flex-wrap: wrap;\">
              <a href=\"/files/generated/{file_id}/download\" target=\"_blank\" rel=\"noreferrer\">Download</a>
              <a id=\"raw-link\" href=\"/files/generated/{file_id}/raw\" target=\"_blank\" rel=\"noreferrer\">Open raw</a>
              <button type=\"button\" onclick=\"copyPreviewText()\">Copy</button>
            </div>
          </div>
          <div class=\"preview-container\">
            {preview_body}
          </div>
          <script>
            function copyPreviewText() {{
              const previewText = document.getElementById('preview-text');
              const rawLink = document.getElementById('raw-link');
              const text = previewText ? previewText.innerText : rawLink ? rawLink.href : '';
              navigator.clipboard.writeText(text).then(function() {{
                alert('Copied to clipboard');
              }}).catch(function() {{
                alert('Copy failed.');
              }});
            }}
          </script>
        </body>
        </html>
    """

    return HTMLResponse(content=page_html, status_code=200)


def _infer_format_from_path(path: Path):
    suffix = path.suffix.lower()
    return {
        ".txt": "txt",
        ".md": "md",
        ".json": "json",
        ".csv": "csv",
        ".pdf": "pdf",
    }.get(suffix, "txt")
