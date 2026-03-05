from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME:str="AI System"
    DATABASE_URL_ASYNC: str
    DATABASE_URL_SYNC: str
    ENV:str="dev"

    class Config:
        env_file=".env"

@lru_cache
def get_settings():
    return Settings()

settings=get_settings()