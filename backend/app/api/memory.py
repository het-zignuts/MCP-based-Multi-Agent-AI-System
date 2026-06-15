from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Message
from app.services.memory.ltm_service import (
    create_memory_with_embedding,
    search_memories_with_scores,
)
from app.services.memory.memory_promoter import promote_memories_from_messages
from app.services.user_profile.user_profile_service import build_user_profile

router = APIRouter(prefix="/memories", tags=["Memories"])


class TestMemoryCreateRequest(BaseModel):
    user_id: UUID
    conversation_id: UUID | None = None
    content: str
    memory_type: str
    memory_metadata: dict = Field(default_factory=dict)
    importance_score: float = 0.5
    source: str = "conversation"


class TestMessageInput(BaseModel):
    role: str
    content: str


class TestPromotionRequest(BaseModel):
    user_id: UUID
    conversation_id: UUID | None = None
    source: str = "conversation"
    messages: list[TestMessageInput]


@router.post("/test-create")
async def test_create_memory(
    payload: TestMemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        memory = await create_memory_with_embedding(
            db,
            user_id=payload.user_id,
            conversation_id=payload.conversation_id,
            content=payload.content,
            memory_type=payload.memory_type,
            memory_metadata=payload.memory_metadata,
            importance_score=payload.importance_score,
            source=payload.source,
        )
        return {
            "id": str(memory.id),
            "content": memory.content,
            "memory_type": memory.memory_type,
            "memory_metadata": memory.memory_metadata,
            "importance_score": memory.importance_score,
            "source": memory.source,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/test-search")
async def test_search_memories(
    user_id: UUID,
    query: str,
    top_k: int = 5,
    memory_type: str | None = None,
    conversation_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        results = await search_memories_with_scores(
            db,
            user_id=user_id,
            query_text=query,
            top_k=top_k,
            memory_type=memory_type,
            conversation_id=conversation_id,
        )

        return [
            {
                "id": str(item["memory"].id),
                "content": item["memory"].content,
                "memory_type": item["memory"].memory_type,
                "memory_metadata": item["memory"].memory_metadata,
                "importance_score": item["memory"].importance_score,
                "source": item["memory"].source,
                "distance": item["distance"],
            }
            for item in results
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/test-promote")
async def test_promote_memories(
    payload: TestPromotionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        fake_messages = [
            Message(role=msg.role, content=msg.content)
            for msg in payload.messages
        ]

        created_memories = await promote_memories_from_messages(
            db,
            user_id=payload.user_id,
            messages=fake_messages,
            conversation_id=payload.conversation_id,
            source=payload.source,
        )

        return {
            "created_count": len(created_memories),
            "created_memories": created_memories,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        profile = await build_user_profile(
            db,
            user_id=user_id,
        )

        return {
            "preferences": profile.preferences,
            "facts": profile.facts,
            "active_goals": profile.active_goals,
            "decisions": profile.decisions,
            "profile_text": profile.to_text(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))