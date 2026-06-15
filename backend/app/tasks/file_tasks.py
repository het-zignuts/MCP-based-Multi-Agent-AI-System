from app.core.celery_app import celery_app
from celery.utils.log import get_task_logger
from app.services.file_processing.file_processing_service import process_and_chunk
from app.services.embeddings.embedding_utils import embed_texts
from app.models.chunks import Chunk
from app.models.file import File
from uuid import UUID
from app.db.database import sync_session_scope

logger = get_task_logger(__name__)


def _set_file_status(file_id: UUID, status: str):
    with sync_session_scope() as sync_db:
        file = sync_db.get(File, file_id)
        if file:
            file.status = status
            sync_db.add(file)
            sync_db.commit()


def _normalize_processed_chunks(chunks):
    processed_chunks = []

    for chunk in chunks:
        if isinstance(chunk, str):
            content = chunk.strip()
            file_metadata = {}
        elif isinstance(chunk, dict):
            content = chunk["content"]
            file_metadata = chunk["metadata"]
        else:
            logger.warning("Invalid chunk type found while processing file task")
            continue

        if content:
            processed_chunks.append((content, file_metadata))

    if not processed_chunks and chunks:
        raise ValueError("No valid chunks were produced during file processing")

    return processed_chunks


def _build_chunk_instances(file_id: UUID, processed_chunks):
    embeddings = embed_texts([content for content, _ in processed_chunks]) if processed_chunks else []
    chunk_instances = []

    for (content, file_metadata), embedding in zip(processed_chunks, embeddings):
        chunk_instance = Chunk(
            file_id=file_id,
            content=content,
            file_metadata=file_metadata,
            embedding=embedding
        )
        chunk_instances.append(chunk_instance)

    return chunk_instances

@celery_app.task(name="app.tasks.file_tasks.process_file")
def process_file(file_id: str, file_path: str):
    print(f"Processing file {file_id}")
    file_uuid = UUID(file_id)

    _set_file_status(file_uuid, "processing")

    try:
        chunks = process_and_chunk(file_path)
        processed_chunks = _normalize_processed_chunks(chunks)
        chunk_instances = _build_chunk_instances(file_uuid, processed_chunks)

        with sync_session_scope() as sync_db:
            sync_db.add_all(chunk_instances)
            sync_db.commit()
        _set_file_status(file_uuid, "processed")

        print(f"File {file_id} processed")
        print(f"Number of chunks: {len(chunks)}")
    except Exception:
        _set_file_status(file_uuid, "failed")
        raise
