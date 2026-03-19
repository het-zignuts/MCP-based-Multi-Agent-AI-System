from fastapi import APIRouter, Depends, UploadFile, File as UploadFileType, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from typing import List

from app.schemas.file import FileCreate, FileRead
from app.crud.file import *
from app.db.database import get_db

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload", response_model=FileRead)
async def upload_file(conversation_id: UUID, user_id: UUID, file: UploadFile = UploadFileType(...), db: AsyncSession = Depends(get_db)):
    path = await save_file_to_storage(file)
    payload = FileCreate(conversation_id=conversation_id, user_id=user_id, filename=file.filename, file_type=file.content_type, file_size=0, storage_path=path)
    return await create_file(db, payload)

@router.get("/{file_id}", response_model=FileRead)
async def read(file_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_file(db, file_id)

@router.get("/", response_model=List[FileRead])
async def read_all(db: AsyncSession = Depends(get_db)):
    return await get_files(db)

@router.put("/{file_id}", response_model=FileRead)
async def update(file_id: UUID, db: AsyncSession = Depends(get_db)):
    file = await get_file(db, file_id)
    updated_file = await update_file(db, file_id, message_id=file.message_id, status=file.status)
    return updated_file   

@router.delete("/{file_id}")
async def delete(file_id: UUID, db: AsyncSession = Depends(get_db)):
    await delete_file(db, file_id)