from celery import Celery

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"}
}
celery_app.conf.imports = ("app.tasks.file_tasks",)

import app.tasks.file_tasks  
