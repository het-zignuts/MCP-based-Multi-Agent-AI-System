from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.ws import router as ws_router
from fastapi.middleware.cors import CORSMiddleware

setup_logging()

app=FastAPI(title="AI System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ws_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}