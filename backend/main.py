from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.openapi import normalize_binary_upload_schema
from app.api.ws import router as ws_router
from app.api.conversation import router as conversation_router
from app.api.user import router as user_router
from app.api.message import router as message_router
from app.api.file import router as file_router
from app.api.file_generation import router as file_generation_router
from app.api.chat import router as chat_router
from app.api.ws import router as ws_router
from  app.services.file_processing.file_task_dispatcher import shutdown_local_file_task_executor
from app.api.memory import router as memory_router
from fastapi.middleware.cors import CORSMiddleware

logger=setup_logging()

app=FastAPI(title="AI System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ws_router)
app.include_router(conversation_router)
app.include_router(user_router)
app.include_router(message_router)
app.include_router(file_router)
app.include_router(file_generation_router)
app.include_router(chat_router)
app.include_router(memory_router)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    normalize_binary_upload_schema(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.on_event("shutdown")
def shutdown_file_task_dispatcher():
    shutdown_local_file_task_executor()
