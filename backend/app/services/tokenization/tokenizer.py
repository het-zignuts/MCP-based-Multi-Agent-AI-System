from functools import lru_cache

from transformers import AutoTokenizer

TOKENIZER_MODEL_NAME = "NousResearch/Llama-2-7b-hf"
FALLBACK_CHARS_PER_TOKEN = 4


@lru_cache(maxsize=1)
def get_tokenizer():
    return AutoTokenizer.from_pretrained(TOKENIZER_MODEL_NAME, local_files_only=True)


def get_token_count(text: str) -> int:
    normalized_text = text or ""

    try:
        tokenizer = get_tokenizer()
        return len(tokenizer.encode(normalized_text))
    except Exception:
        # Keep STM available even when the tokenizer model is not cached locally.
        return max(1, (len(normalized_text) + FALLBACK_CHARS_PER_TOKEN - 1) // FALLBACK_CHARS_PER_TOKEN)
