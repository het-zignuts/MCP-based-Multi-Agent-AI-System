import asyncio
from collections import defaultdict

from loguru import logger
from sqlmodel import select

from app.crud.memory import touch_memory
from app.db.database import AsyncSessionLocal
from app.db.models import Memory
from app.services.memory.memory_metadata_annotator import (
    annotate_memory_profile_metadata,
)
from app.services.memory.user_profile_cache_service import refresh_user_profile_cache


def _needs_profile_backfill(memory: Memory) -> bool:
    metadata = getattr(memory, "memory_metadata", {}) or {}
    return (
        "profile_category" not in metadata
        or "profile_attributes" not in metadata
    )


async def backfill_profile_metadata() -> dict[str, int]:
    updated_count = 0
    skipped_count = 0
    refreshed_users: set[str] = set()
    memories_by_user: dict[str, list[Memory]] = defaultdict(list)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Memory).where(Memory.is_active == True).order_by(Memory.updated_at.desc())
        )
        memories = list(result.scalars().all())

        for memory in memories:
            memories_by_user[str(memory.user_id)].append(memory)

        for memory in memories:
            if not _needs_profile_backfill(memory):
                skipped_count += 1
                continue

            annotation = await annotate_memory_profile_metadata(
                content=memory.content,
                memory_type=memory.memory_type,
            )
            updated_metadata = {
                **(memory.memory_metadata or {}),
                "profile_category": annotation["profile_category"],
                "profile_attributes": annotation["profile_attributes"],
                "profile_annotation_confidence": annotation["confidence"],
            }

            await touch_memory(
                db,
                memory.id,
                memory_metadata=updated_metadata,
            )
            updated_count += 1
            refreshed_users.add(str(memory.user_id))

        for user_id in refreshed_users:
            await refresh_user_profile_cache(db, user_id=user_id)

    return {
        "updated_memories": updated_count,
        "skipped_memories": skipped_count,
        "refreshed_users": len(refreshed_users),
    }


async def _main() -> None:
    result = await backfill_profile_metadata()
    logger.info("Profile metadata backfill complete | result={}", result)
    print(result)


if __name__ == "__main__":
    asyncio.run(_main())
