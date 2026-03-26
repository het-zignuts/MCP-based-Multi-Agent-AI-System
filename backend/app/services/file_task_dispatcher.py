from concurrent.futures import ThreadPoolExecutor

from fastapi import BackgroundTasks
from kombu.exceptions import OperationalError

from app.core.config import settings
from app.core.celery_app import celery_app

LOCAL_FILE_TASK_EXECUTOR: ThreadPoolExecutor | None = None


def get_local_file_task_executor() -> ThreadPoolExecutor:
    global LOCAL_FILE_TASK_EXECUTOR
    if LOCAL_FILE_TASK_EXECUTOR is None:
        LOCAL_FILE_TASK_EXECUTOR = ThreadPoolExecutor(max_workers=2)
    return LOCAL_FILE_TASK_EXECUTOR


def shutdown_local_file_task_executor() -> None:
    global LOCAL_FILE_TASK_EXECUTOR
    if LOCAL_FILE_TASK_EXECUTOR is not None:
        LOCAL_FILE_TASK_EXECUTOR.shutdown(wait=True)
        LOCAL_FILE_TASK_EXECUTOR = None


def _process_file_locally(file_id: str, storage_path: str) -> None:
    from app.tasks.file_tasks import process_file

    process_file(file_id, storage_path)


def _submit_local_file_processing(file_id: str, storage_path: str) -> None:
    get_local_file_task_executor().submit(_process_file_locally, file_id, storage_path)


def _enqueue_with_celery(file_id: str, storage_path: str) -> None:
    celery_app.send_task(
        "app.tasks.file_tasks.process_file",
        args=[file_id, storage_path],
    )


def queue_file_processing(
    background_tasks: BackgroundTasks,
    file_id: str,
    storage_path: str,
) -> None:
    if settings.FILE_PROCESSING_BACKEND == "celery" and settings.CELERY_BROKER_URL:
        try:
            _enqueue_with_celery(file_id, storage_path)
            return
        except OperationalError:
            # Fall back to in-process execution when the broker is unavailable.
            pass

    background_tasks.add_task(_submit_local_file_processing, file_id, storage_path)
