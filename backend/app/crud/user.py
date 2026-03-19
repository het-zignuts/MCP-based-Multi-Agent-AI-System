from sqlmodel import select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from uuid import UUID

from app.db.models import User

async def create_user(db: AsyncSession, payload) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, password=payload.password)
    db.add(user)
    await db.commit()
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.conversations))
    )
    user = result.scalar_one()
    return user

async def get_user(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.conversations)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email).options(selectinload(User.conversations)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).options(selectinload(User.conversations)))
    users = result.scalars().all()
    return users

async def update_user(db: AsyncSession, user_id: UUID, email: str | None = None, password: str | None = None, is_active: bool | None = None) -> User:
    user = await get_user(db, user_id)
    # Email update with uniqueness check
    if email and email != user.email:
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = email
    if password:
        user.password = password  # hash later
    if is_active is not None:
        user.is_active = is_active

    await db.commit()
    await db.refresh(user)
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.conversations))
    )
    user = result.scalar_one()

    return user
async def delete_user(db: AsyncSession, user_id: UUID) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)
    await db.commit()