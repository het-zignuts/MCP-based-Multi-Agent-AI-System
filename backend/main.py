from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

app=FastAPI(title="AI System", version="1.0.0")

@app.get("/health")
async def health_check():
    return {"status": "ok"}