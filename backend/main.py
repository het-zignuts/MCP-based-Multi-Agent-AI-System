from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.ws import router as ws_router

setup_logging()

app=FastAPI(title="AI System", version="1.0.0")

app.include_router(ws_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}