from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from typing import List

from app.schemas.user import UserCreate, UserRead
from app.crud.user import *
from app.db.database import get_db

router = APIRouter()

@router.post("/", response_model=UserRead)
async def create(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user

@router.get("/{user_id}", response_model=UserRead)
async def read(user_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_user(db, user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return user

@router.get("/", response_model=List[UserRead])
async def read_all(db: AsyncSession = Depends(get_db)):
    try:
        users = await get_users(db)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return users

@router.put("/{user_id}", response_model=UserRead)
async def update(user_id: UUID, email: str, password: str, is_active: bool, db: AsyncSession = Depends(get_db)):
    try:
        updated_user = await update_user(db, user_id, email=email, password=password, is_active=is_active)
        return updated_user
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{user_id}")
async def delete(user_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await delete_user(db, user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))