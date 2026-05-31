import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from celery import Celery
from celery.signals import worker_ready

from src.common.config import get_settings

settings = get_settings()

celery = Celery(
    "netops_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.core.celery_tasks.tasks", "src.core.workflows.tasks"]
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


@worker_ready.connect
def _on_worker_ready(**kwargs):
    """Celery Worker 启动后订阅 Workflow 热重载广播。"""
    from src.core.workflows.reload_bus import start_reload_listener

    start_reload_listener()
    print("[Celery] Workflow 多 Worker 热重载监听已启动")

celery.autodiscover_tasks(["src.core.celery_tasks"])

if __name__ == "__main__":
    celery.start()
