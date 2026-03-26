from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME:str="AI System"
    DATABASE_URL_ASYNC: str
    DATABASE_URL_SYNC: str
    ENV:str="dev"
    MODEL: str | None = None
    GROQ_API_KEY: str | None = None
    LLM_TEMPERATURE: float = 0.2
    FILE_PROCESSING_BACKEND: str = "local"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    class Config:
        env_file=".env"

@lru_cache
def get_settings():
    return Settings()

settings=get_settings()
