import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from tree_sitter_languages import get_language, get_parser
from typing import List, Dict
import os
import pandas as pd

def clean_pdf_text(text: str) -> str:
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def chunk_pdf(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    return splitter.split_text(text)

def chunk_markdown_and_docx(text: str):
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on
    )
    docs = splitter.split_text(text)
    return [doc.page_content for doc in docs]

def chunk_txt(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_text(text)

def recursive_character_chunking_for_images(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap     
    return chunks

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
}


def get_language_from_filename(filename: str):
    ext = os.path.splitext(filename)[1]
    lang_name = EXTENSION_LANGUAGE_MAP.get(ext)
    if not lang_name:
        return None
    return get_language(lang_name), get_parser(lang_name)


def chunk_code_ast(code: str, filename: str) -> List[Dict]:
    """
    AST-based chunking using Tree-sitter
    """
    print("AST STEP 1: getting language")
    lang = get_language_from_filename(filename)
    if not lang:
        print("AST STEP 2: fallback")
        return fallback_chunk(code, filename)

    _, parser = lang
    print("AST STEP 3: parsing started")
    tree = parser.parse(bytes(code, "utf-8"))
    print("AST STEP 4: parsing finished")
    root = tree.root_node

    chunks = []

    def traverse(node, depth=0):
        """
        Recursively extract meaningful chunks
        """
        important_types = {
            "function_definition",
            "class_definition",
            "method_definition",
            "function_declaration",
            "class_declaration",
            "generator_function_declaration",
            "lexical_declaration",
            "variable_declaration",
            "public_field_definition",
        }
        print(f"Traversing node: {node.type}")
        if node.type in important_types:
            start_byte = node.start_byte
            end_byte = node.end_byte

            chunk_text = code[start_byte:end_byte]

            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "filename": filename,
                    "type": node.type,
                    "start_byte": start_byte,
                    "end_byte": end_byte,
                }
            })
        
        for child in node.children:
            traverse(child, depth + 1)

    traverse(root)
    print("Traversal done")
    if not chunks:
        print("Calling Fallback")
        return fallback_chunk(code, filename)
    print("Returning chunks")
    return chunks

def fallback_chunk(code: str, filename: str, chunk_size=1000, overlap=100):
    """
    Line/char-based fallback chunking
    """
    chunks = []
    start = 0
    step = max(chunk_size - overlap, 1)

    while start < len(code):
        end = min(start + chunk_size, len(code))
        chunk = code[start:end]

        chunks.append({
            "content": chunk,
            "metadata": {
                "filename": filename,
                "type": "fallback",
                "start": start,
                "end": end,
            }
        })

        if end >= len(code):
            break

        start += step

    return chunks

def chunk_dataframe(df: pd.DataFrame, filename: str, chunk_size: int = 100) -> List[Dict]:
    """
    Chunk dataframe into row-based chunks
    """
    chunks = []
    total_rows = len(df)

    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)

        chunk_df = df.iloc[start:end]
        chunk_text = chunk_df.to_csv(index=False)

        chunks.append({
            "content": chunk_text,
            "metadata": {
                "filename": filename,
                "type": "table_chunk",
                "start_row": start,
                "end_row": end,
                "columns": list(df.columns),
            }
        })

    return chunks

def chunk_xlsx(file_path: str) -> List[Dict]:
    chunks = []

    excel_file = pd.ExcelFile(file_path)
    for sheet_name in excel_file.sheet_names:
        df = excel_file.parse(sheet_name)

        sheet_chunks = chunk_dataframe(df, file_path)
        for chunk in sheet_chunks:
            chunk["metadata"]["sheet"] = sheet_name
        chunks.extend(sheet_chunks)
    return chunks
