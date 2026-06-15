from datetime import datetime

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile_snapshot import UserProfileSnapshot


async def get_user_profile_snapshot(
    db: AsyncSession,
    *,
    user_id,
) -> UserProfileSnapshot | None:
    result = await db.execute(
        select(UserProfileSnapshot).where(UserProfileSnapshot.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_user_profile_snapshot(
    db: AsyncSession,
    *,
    user_id,
    profile_text: str,
    profile_items: list[dict],
    preferences: list[str],
    facts: list[str],
    active_goals: list[str],
    decisions: list[str],
    source_memory_count: int,
) -> UserProfileSnapshot:
    existing = await get_user_profile_snapshot(db, user_id=user_id)

    if existing:
        existing.profile_text = profile_text
        existing.profile_items = profile_items
        existing.preferences = preferences
        existing.facts = facts
        existing.active_goals = active_goals
        existing.decisions = decisions
        existing.source_memory_count = source_memory_count
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    snapshot = UserProfileSnapshot(
        user_id=user_id,
        profile_text=profile_text,
        profile_items=profile_items,
        preferences=preferences,
        facts=facts,
        active_goals=active_goals,
        decisions=decisions,
        source_memory_count=source_memory_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
