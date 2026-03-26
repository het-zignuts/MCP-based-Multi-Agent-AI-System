from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from sqlmodel import create_engine, Session
from contextlib import contextmanager

engine=create_async_engine(settings.DATABASE_URL_ASYNC, echo=True)

AsyncSessionLocal=sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=True)
def get_sync_session():
    with Session(sync_engine) as session:
        yield session

@contextmanager
def sync_session_scope():
    with Session(sync_engine) as session:
        yield session
