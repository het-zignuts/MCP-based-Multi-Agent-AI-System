import os
import re
import zipfile
from typing import Any

import PyPDF2
import pandas as pd
from docx import Document
import pytesseract
from fastapi import HTTPException
from PIL import Image
from app.services.file_chunkers import *


MAX_OFFICE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def validate_office_archive(file_path: str) -> None:
    with zipfile.ZipFile(file_path) as archive:
        total_uncompressed_size = sum(file_info.file_size for file_info in archive.infolist())

    if total_uncompressed_size > MAX_OFFICE_UNCOMPRESSED_BYTES:
        raise HTTPException(status_code=400, detail="Office file is too large to process safely")

def process_pdf(file_path: str) -> list[str]:
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        content= "\n".join([page.extract_text() or "" for page in reader.pages])
        chunks=chunk_pdf(content)
        return chunks

def process_markdown(file_path: str) -> list[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join([line.rstrip() for line in text.split("\n")])
    text = text.strip()
    chunks=chunk_markdown_and_docx(text)
    return chunks

def process_docx(file_path: str) -> list[str]:
    validate_office_archive(file_path)
    doc = Document(file_path)
    structured_text = []
    for para in doc.paragraphs:
        style = para.style.name
        if style.startswith("Heading"):
            level = style.replace("Heading ", "")
            structured_text.append(f"\n{'#' * int(level)} {para.text}\n")
        else:
            structured_text.append(para.text)
    content_str= "\n".join(structured_text)
    chunks=chunk_markdown_and_docx(content_str)
    return chunks

def process_text(file_path: str) -> list[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        text= f.read()
    chunks=chunk_txt(text)
    return chunks

def process_image(file_path: str) -> list[str]:
    image = Image.open(file_path).convert("RGB")
    img_text = pytesseract.image_to_string(image).strip()
    if not img_text:
        return []
    chunks=recursive_character_chunking_for_images(img_text)
    return chunks

def process_code(file_path: str) -> list[dict[str, Any]]:
    print("STEP 1: reading file")
    with open(file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    print("STEP 2: file read done")
    filename = os.path.basename(file_path)
    print("STEP 3: calling AST chunking")
    chunks = chunk_code_ast(file_content, filename)
    print("STEP 4: chunking done")
    return chunks

def process_csv(file_path: str) -> list[dict[str, Any]]:
    df = pd.read_csv(file_path)
    chunks=chunk_dataframe(df, file_path)
    return chunks

def process_xlsx(file_path: str) -> list[dict[str, Any]]:
    validate_office_archive(file_path)
    chunks=chunk_xlsx(file_path)
    return chunks
