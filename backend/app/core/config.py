from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"
load_dotenv(str(ENV_FILE))

class Settings(BaseSettings):
    APP_NAME:str="AI System"
    DATABASE_URL_ASYNC: str
    DATABASE_URL_SYNC: str
    ENV:str="dev"
    MODEL: str | None = None
    CHAT_MODEL: str | None = None
    MAINTENANCE_MODEL: str | None = None
    AGENT_MODEL: str = "gemini-3.1-flash-lite"  # Model used by ADK agents (2.0-flash: 1500 RPD free)
    AGENT_FALLBACK_MODEL: str | None = "groq/llama-3.3-70b-versatile"  # Fallback when primary is quota-exhausted
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_WORKERS: int = 4
    MAINTENANCE_LLM_MAX_WORKERS: int = 1
    MAINTENANCE_MAX_COMPARISONS_PER_RUN: int = 6
    MAINTENANCE_MIN_COMPARISONS_FOR_OPTIONAL_STAGES: int = 1
    MAINTENANCE_MIN_COMPARISONS_FOR_PROFILE_REFRESH: int = 1
    PROFILE_MAX_LLM_COMPARISONS_PER_REFRESH: int = 3
    PROFILE_DUPLICATE_SIMILARITY_THRESHOLD: float = 0.92
    PROFILE_CONFLICT_SIMILARITY_THRESHOLD: float = 0.82
    FILE_PROCESSING_BACKEND: str = "local"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    class Config:
        env_file = str(ENV_FILE)

@lru_cache
def get_settings():
    return Settings()

settings=get_settings()
