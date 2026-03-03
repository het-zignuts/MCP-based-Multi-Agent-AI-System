from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine=create_async_engine(settngs.DATABASE_URL, echo=True)

AsyncSessionLocal=sessionmaker(bind=engine, class_=AsyncSession, expires_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session