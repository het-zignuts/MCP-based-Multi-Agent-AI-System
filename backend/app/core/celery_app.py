import platform

from celery import Celery
from app.core.config import settings

celery_kwargs = {}
if settings.CELERY_BROKER_URL:
    celery_kwargs["broker"] = settings.CELERY_BROKER_URL
if settings.CELERY_RESULT_BACKEND:
    celery_kwargs["backend"] = settings.CELERY_RESULT_BACKEND

celery_app = Celery(
    "worker",
    **celery_kwargs,
)

celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"}
}
celery_app.conf.imports = ("app.tasks.file_tasks",)
celery_app.conf.broker_connection_retry_on_startup = True

# macOS + prefork can crash when native ML frameworks initialize across forked workers.
if platform.system() == "Darwin":
    celery_app.conf.worker_pool = "solo"
    celery_app.conf.worker_concurrency = 1

import app.tasks.file_tasks  
