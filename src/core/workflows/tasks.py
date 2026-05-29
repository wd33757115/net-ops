"""Workflow Celery 任务调度。"""

from __future__ import annotations

import logging

from src.core.celery_tasks.celery_app import celery
from src.core.workflows.engine import WorkflowEngine
from src.core.workflows.repository import list_workflow_steps, mark_step_failed

logger = logging.getLogger(__name__)


def _get_celery_task(task_name: str):
    from src.core.celery_tasks import tasks as task_module

    return getattr(task_module, task_name, None)


@celery.task(bind=True, name="dispatch_workflow_step_task")
def dispatch_workflow_step_task(self, run_id: str, step_index: int):
    """调度 Workflow 单步 Celery 子任务。"""
    from src.core.workflows.templates import TEMPLATES
    from src.core.workflows.repository import get_workflow_run

    run = get_workflow_run(run_id)
    if not run:
        return {"success": False, "error": "workflow run not found"}

    template = TEMPLATES.get(run.template_name)
    steps = list_workflow_steps(run_id)
    if not template or step_index >= len(steps):
        return {"success": False, "error": "invalid step"}

    step_tpl = template.steps[step_index]
    params = WorkflowEngine.build_step_params(run_id, step_index)
    task_func = _get_celery_task(step_tpl.celery_task)
    if not task_func:
        mark_step_failed(steps[step_index].id, f"任务未注册: {step_tpl.celery_task}")
        WorkflowEngine.handle_step_complete(run_id, step_index, {"success": False, "error": "task not found"})
        return {"success": False}

    try:
        # 在 Worker 任务内直接调用 run()，避免 apply/asyncResult.get 触发 Celery 死锁检测
        result = task_func.run(**params)
        WorkflowEngine.handle_step_complete(run_id, step_index, result)
        return result
    except Exception as exc:
        logger.exception("Workflow 步骤执行异常 run=%s step=%s", run_id, step_index)
        WorkflowEngine.handle_step_complete(run_id, step_index, {"success": False, "error": str(exc)})
        raise
