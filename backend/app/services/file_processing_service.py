from typing import Any

import os
from app.services.file_processors import *
from app.services.file_type_config import (
    CODE_FILE_EXTENSIONS,
    IMAGE_FILE_EXTENSIONS,
    TEXT_FILE_EXTENSIONS,
)

def process_and_chunk(file_path: str) -> list[str] | list[dict[str, Any]]:
    filename=os.path.basename(file_path)
    extension = os.path.splitext(filename)[1].lower()
    
    if extension==".pdf":
        chunks=process_pdf(file_path)
    elif extension==".docx":
        chunks=process_docx(file_path)
    elif extension in TEXT_FILE_EXTENSIONS:
        chunks=process_text(file_path)
    elif extension==".md":
        chunks=process_markdown(file_path)
    elif extension==".csv":
        chunks=process_csv(file_path)
    elif extension==".xlsx":
        chunks=process_xlsx(file_path)
    elif extension in CODE_FILE_EXTENSIONS:
        chunks=process_code(file_path)
    elif extension in IMAGE_FILE_EXTENSIONS:
        chunks=process_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {filename}")
    
    return chunks
