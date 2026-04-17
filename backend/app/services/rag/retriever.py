from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.db.models.chunks import Chunk
from app.db.models.file import File
from app.services.embeddings.embedding_utils import embed_text_async
from app.services.timing import log_async_timing

async def retrieve_similar_chunks(
    query_embedding,
    file_ids,
    conversation_id,
    user_id,
    db: AsyncSession,
    top_k=5,
):
    if not file_ids:
        return []

    query = (
        select(
            Chunk.id.label("id"),
            Chunk.content.label("content"),
            Chunk.file_metadata.label("metadata"),
        )
        .join(File, File.id == Chunk.file_id)
        .where(
            Chunk.file_id.in_(file_ids),
            File.conversation_id == conversation_id,
            File.user_id == user_id,
            File.status == "processed",
        )
        .order_by(Chunk.embedding.l2_distance(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(query)

    rows = result.mappings().all()

    return rows

def build_context(chunks):
    context = "\n\n---\n\n".join(
        [chunk["content"] for chunk in chunks]
    )
    return context

async def get_processed_file_ids(
    conversation_id,
    user_id,
    db: AsyncSession,
    limit: int = 12,
    file_ids: list | None = None,
):
    query = (
        select(File.id)
        .where(
            File.conversation_id == conversation_id,
            File.user_id == user_id,
            File.status == "processed",
        )
        .order_by(File.created_at.desc())
        .limit(limit)
    )
    if file_ids:
        query = query.where(File.id.in_(file_ids))

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_pending_file_names(
    conversation_id,
    user_id,
    db: AsyncSession,
    file_ids: list | None = None,
):
    if not file_ids:
        return []

    result = await db.execute(
        select(File.filename)
        .where(
            File.id.in_(file_ids),
            File.conversation_id == conversation_id,
            File.user_id == user_id,
            File.status != "processed",
        )
        .order_by(File.created_at.desc())
    )
    return list(result.scalars().all())

@log_async_timing("retrieve_pipeline")
async def retrieve_pipeline(
    query: str,
    file_ids,
    conversation_id,
    user_id,
    db: AsyncSession,
):
    prioritized_file_ids = await get_processed_file_ids(
        conversation_id,
        user_id,
        db,
        file_ids=file_ids,
    )
    if prioritized_file_ids:
        searchable_file_ids = prioritized_file_ids
    else:
        searchable_file_ids = await get_processed_file_ids(
            conversation_id,
            user_id,
            db,
        )

    pending_file_names = await get_pending_file_names(
        conversation_id,
        user_id,
        db,
        file_ids=file_ids,
    )

    if not searchable_file_ids:
        if pending_file_names:
            pending_files = "\n".join(f"- {name}" for name in pending_file_names)
            return (
                "Attached files are still being processed and are not searchable yet:\n"
                f"{pending_files}"
            )
        return ""

    user_query = await embed_text_async(query)
    similar_chunks = await retrieve_similar_chunks(
        user_query,
        searchable_file_ids,
        conversation_id,
        user_id,
        db,
    )
    context = build_context(similar_chunks)
    if pending_file_names:
        pending_files = "\n".join(f"- {name}" for name in pending_file_names)
        pending_notice = (
            "Attached files still processing and not yet included in retrieval:\n"
            f"{pending_files}"
        )
        return f"{pending_notice}\n\n---\n\n{context}" if context else pending_notice
    return context
