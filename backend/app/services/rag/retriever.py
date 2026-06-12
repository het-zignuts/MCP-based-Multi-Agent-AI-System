from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models.chunks import Chunk
from app.db.models.file import File
from app.services.embeddings.embedding_utils import embed_text_async
from  app.services.time.timing import log_async_timing


MMR_LAMBDA = 0.7
MMR_CANDIDATE_MULTIPLIER = 4
SECTION_SCORE_MARGIN = 0.08
MULTI_SECTION_LIMIT = 2


def _to_numpy(vector: list[float] | tuple[float, ...] | None) -> np.ndarray | None:
    if vector is None:
        return None
    array = np.asarray(vector, dtype=float)
    if array.size == 0:
        return None
    return array


def _cosine_similarity(left: np.ndarray | None, right: np.ndarray | None) -> float:
    if left is None or right is None:
        return 0.0

    left_norm = np.linalg.norm(left)
    right_norm = np.linalg.norm(right)
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return float(np.dot(left, right) / (left_norm * right_norm))


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())


def _section_key(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    return (
        str(metadata.get("section_id"))
        or str(metadata.get("sheet"))
        or str(metadata.get("filename"))
        or str(chunk.get("id"))
    )


def _section_label(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    for key in ("section_title", "sheet", "filename", "type"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _section_title_match_score(query_text: str, section_label: str) -> float:
    normalized_query = _normalize_text(query_text)
    normalized_label = _normalize_text(section_label)
    if not normalized_query or not normalized_label:
        return 0.0

    if normalized_label in normalized_query:
        return 0.35

    query_tokens = set(normalized_query.split())
    label_tokens = set(normalized_label.split())
    if not query_tokens or not label_tokens:
        return 0.0

    overlap = len(query_tokens & label_tokens) / len(label_tokens)
    if overlap >= 0.8:
        return 0.25
    if overlap >= 0.5:
        return 0.12
    return 0.0


def _select_section_scoped_chunks(
    chunks: list[dict[str, Any]],
    query_text: str,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    grouped_sections: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        key = _section_key(chunk)
        section = grouped_sections.setdefault(
            key,
            {"chunks": [], "label": _section_label(chunk)},
        )
        section["chunks"].append(chunk)
        if not section["label"]:
            section["label"] = _section_label(chunk)

    if len(grouped_sections) <= 1:
        return chunks

    ranked_sections: list[dict[str, Any]] = []
    for key, section in grouped_sections.items():
        section_chunks = section["chunks"]
        ranked_relevances = sorted(
            (float(chunk.get("relevance", 0.0)) for chunk in section_chunks),
            reverse=True,
        )
        best_relevance = ranked_relevances[0] if ranked_relevances else 0.0
        mean_top_relevance = (
            sum(ranked_relevances[:2]) / min(len(ranked_relevances), 2)
            if ranked_relevances
            else 0.0
        )
        title_match_boost = _section_title_match_score(query_text, section["label"])
        section_score = best_relevance + (0.15 * mean_top_relevance) + title_match_boost
        ranked_sections.append(
            {
                "key": key,
                "chunks": section_chunks,
                "label": section["label"],
                "score": section_score,
                "title_match_boost": title_match_boost,
            }
        )

    ranked_sections.sort(key=lambda section: section["score"], reverse=True)
    top_section = ranked_sections[0]
    second_score = ranked_sections[1]["score"] if len(ranked_sections) > 1 else float("-inf")

    if (
        top_section["title_match_boost"] > 0.0
        or top_section["score"] >= second_score + SECTION_SCORE_MARGIN
    ):
        return top_section["chunks"]

    selected_sections = ranked_sections[:MULTI_SECTION_LIMIT]
    allowed_keys = {section["key"] for section in selected_sections}
    return [chunk for chunk in chunks if _section_key(chunk) in allowed_keys]


def _mmr_select_chunks(
    chunks: list[dict[str, Any]],
    query_embedding,
    *,
    top_k: int,
    lambda_mult: float = MMR_LAMBDA,
) -> list[dict[str, Any]]:
    if len(chunks) <= top_k:
        return chunks

    query_vector = _to_numpy(query_embedding)
    candidate_items: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_vector = _to_numpy(chunk.get("embedding"))
        candidate_items.append(
            {
                "chunk": chunk,
                "vector": chunk_vector,
                "relevance": float(chunk.get("relevance", _cosine_similarity(query_vector, chunk_vector))),
            }
        )

    selected_items: list[dict[str, Any]] = []
    remaining_items = candidate_items.copy()

    first_item = max(remaining_items, key=lambda item: item["relevance"])
    selected_items.append(first_item)
    remaining_items.remove(first_item)

    while remaining_items and len(selected_items) < top_k:
        best_item = None
        best_score = float("-inf")

        for item in remaining_items:
            novelty_penalty = max(
                (
                    _cosine_similarity(item["vector"], selected["vector"])
                    for selected in selected_items
                ),
                default=0.0,
            )
            mmr_score = (
                lambda_mult * item["relevance"]
                - (1.0 - lambda_mult) * novelty_penalty
            )
            if mmr_score > best_score:
                best_score = mmr_score
                best_item = item

        if best_item is None:
            break

        selected_items.append(best_item)
        remaining_items.remove(best_item)

    return [item["chunk"] for item in selected_items]

async def retrieve_similar_chunks(
    query_text: str,
    query_embedding,
    file_ids,
    conversation_id,
    user_id,
    db: AsyncSession,
    top_k=5,
    candidate_limit: int | None = None,
):
    if not file_ids:
        return []

    candidate_limit = candidate_limit or max(top_k * MMR_CANDIDATE_MULTIPLIER, top_k)

    query = (
        select(
            Chunk.id.label("id"),
            Chunk.content.label("content"),
            Chunk.file_metadata.label("metadata"),
            Chunk.embedding.label("embedding"),
        )
        .join(File, File.id == Chunk.file_id)
        .where(
            Chunk.file_id.in_(file_ids),
            File.conversation_id == conversation_id,
            File.user_id == user_id,
            File.status == "processed",
        )
        .order_by(Chunk.embedding.l2_distance(query_embedding))
        .limit(candidate_limit)
    )
    result = await db.execute(query)
    rows = [dict(row) for row in result.mappings().all()]
    query_vector = _to_numpy(query_embedding)
    for row in rows:
        row["relevance"] = _cosine_similarity(query_vector, _to_numpy(row.get("embedding")))

    scoped_rows = _select_section_scoped_chunks(rows, query_text)
    return _mmr_select_chunks(scoped_rows, query_embedding, top_k=top_k)

def build_context(chunks):
    context_blocks: list[str] = []
    last_section_key = None

    for chunk in chunks:
        content = (chunk.get("content") or "").strip()
        if not content:
            continue

        current_section_key = _section_key(chunk)
        current_section_label = _section_label(chunk)
        if current_section_key != last_section_key and current_section_label:
            context_blocks.append(f"Section: {current_section_label}")

        context_blocks.append(content)
        last_section_key = current_section_key

    return "\n\n---\n\n".join(context_blocks)

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
        query,
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
