import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from celery import Celery

from src.common.config import get_settings

settings = get_settings()

celery = Celery(
    "netops_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.core.celery_tasks.tasks"]
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    default_retry_delay=60,
    max_retries=settings.CELERY_MAX_RETRIES,
)

celery.autodiscover_tasks(["src.core.celery_tasks"])

if __name__ == "__main__":
    celery.start()
