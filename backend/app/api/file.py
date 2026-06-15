from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from uuid import UUID
from app.schemas.file import FileCreate, FileRead
from app.crud.file import (create_file, get_file, get_files, validate_and_save_file_to_storage)
from app.db.database import get_db
from app.services.file_processing.file_task_dispatcher import queue_file_processing
from app.models import Conversation

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload", response_model=list[FileRead])
async def upload_file(
    background_tasks: BackgroundTasks,
    conversation_id: UUID = Query(..., alias="conversation_id"),
    files: list[UploadFile] = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
):
    conversation = (
        await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    created_files = []
    queued_jobs: list[tuple[str, str]] = []
    for file in files:
        path, size = await validate_and_save_file_to_storage(file)
        payload = FileCreate(
            conversation_id=conversation_id,
            user_id=conversation.user_id,
            filename=file.filename,
            file_type=file.content_type,
            file_size=size,
            storage_path=path,
        )
        file_created = await create_file(db, payload)
        queued_jobs.append((str(file_created.id), file_created.storage_path))
        validated_file = FileRead(**file_created.model_dump())
        created_files.append(validated_file)

    await db.commit()
    for file_id, storage_path in queued_jobs:
        queue_file_processing(background_tasks, file_id, storage_path)
    return created_files
@router.get("/{file_id}", response_model=FileRead)
async def read(file_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_file(db, file_id)

@router.get("/", response_model=List[FileRead])
async def read_all(conversation_id: UUID, message_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    return await get_files(db, conversation_id, message_id)


@router.put("/{file_id}", response_model=FileRead)
async def update(file_id: UUID, message_id: UUID | None = None, status: str | None = None, db: AsyncSession = Depends(get_db)):
    raise HTTPException(
        status_code=501,
        detail="File updates require authenticated user context and are currently disabled.",
    )

@router.delete("/{file_id}")
async def delete(file_id: UUID, db: AsyncSession = Depends(get_db)):
    raise HTTPException(
        status_code=501,
        detail="File deletes require authenticated user context and are currently disabled.",
    )
