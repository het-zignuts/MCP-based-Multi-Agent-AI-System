from app.core.celery_app import celery_app
from celery.utils.log import get_task_logger
from app.services.file_processing_service import *
import time

logger = get_task_logger(__name__)

@celery_app.task(name="app.tasks.file_tasks.process_file")
def process_file(file_id: str, file_path: str):
    print(f"Processing file {file_id}")
    chunks=process_and_chunk(file_path)
    print(f"File {file_id} processed")
    print(f"Number of chunks: {len(chunks)}")
    for chunk in chunks:
        print(chunk)
        time.sleep(1)