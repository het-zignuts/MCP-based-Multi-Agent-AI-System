from typing import List
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from app.schemas.file import FileCreate, FileRead
from app.crud.file import (create_file, get_file, get_files, update_file, delete_file, validate_and_save_file_to_storage)
from app.db.database import get_db
from app.tasks.file_tasks import process_file

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload", response_model=list[FileRead])
async def upload_file(
    conversation_id: UUID = Query(..., alias="conversation_id"),
    user_id: UUID = Query(..., alias="user_id"),
    files: list[UploadFile] = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
):
    created_files = []
    for file in files:
        path, size = await validate_and_save_file_to_storage(file)
        payload = FileCreate(conversation_id=conversation_id, user_id=user_id, filename=file.filename, file_type=file.content_type, file_size=size, storage_path=path)
        file_created = await create_file(db, payload)
        process_file.delay(str(file_created.id), file_created.storage_path)
        validated_file = FileRead(**file_created.model_dump())
        created_files.append(validated_file)
    return created_files
@router.get("/{file_id}", response_model=FileRead)
async def read(file_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_file(db, file_id)

@router.get("/", response_model=List[FileRead])
async def read_all(conversation_id: UUID, message_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    return await get_files(db, conversation_id, message_id)

@router.put("/{file_id}", response_model=FileRead)
async def update(file_id: UUID, message_id: UUID | None = None, status: str | None = None, db: AsyncSession = Depends(get_db)):
    file = await get_file(db, file_id)
    updated_file = await update_file(db, file_id, message_id=message_id, status=status)
    return updated_file   

@router.delete("/{file_id}")
async def delete(file_id: UUID, db: AsyncSession = Depends(get_db)):
    await delete_file(db, file_id)
