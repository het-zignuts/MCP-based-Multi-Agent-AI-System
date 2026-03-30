import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

_embed_model = None
EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=4)
atexit.register(lambda: EMBEDDING_EXECUTOR.shutdown(wait=False))

def get_embed_model():
    """Return a HuggingFace embedding model for semantic vectors."""
    global _embed_model
    if _embed_model is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embed_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embed_model

def embed_text(text: str):
    """Generate a semantic vector for a given text."""
    return get_embed_model().embed_query(text)

async def embed_text_async(text: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(EMBEDDING_EXECUTOR, embed_text, text)

def embed_texts(texts: list[str]):
    """Generate semantic vectors for multiple texts in a single batch."""
    return get_embed_model().embed_documents(texts)