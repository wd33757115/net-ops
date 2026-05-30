"""Workflow Celery 任务调度。"""

from __future__ import annotations

import logging

from src.core.celery_tasks.celery_app import celery
from src.core.workflows.engine import WorkflowEngine
from src.core.workflows.registry import find_step_template, get_template
from src.core.workflows.repository import get_workflow_run, list_workflow_steps, mark_step_failed

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="execute_skill_task")
def execute_skill_task(self, skill_name: str, **params):
    """通用 Skill 执行 Celery 任务。"""
    from src.core.skills.executor import SkillExecutionError, execute_skill

    try:
        return execute_skill(skill_name, params)
    except SkillExecutionError as exc:
        return {"success": False, "message": str(exc), "error": str(exc)}


@celery.task(bind=True, name="dispatch_workflow_step_task")
def dispatch_workflow_step_task(self, run_id: str, step_index: int):
    """调度 Workflow 单步 Skill（通过 execute_skill_task）。"""
    run = get_workflow_run(run_id)
    if not run:
        return {"success": False, "error": "workflow run not found"}

    template = get_template(run.template_name)
    steps = list_workflow_steps(run_id)
    if not template or step_index >= len(steps):
        return {"success": False, "error": "invalid step"}

    step_rec = steps[step_index]
    step_tpl = find_step_template(template, step_rec.step_name)
    if not step_tpl:
        return {"success": False, "error": f"unknown step: {step_rec.step_name}"}
    params = WorkflowEngine.build_step_params(run_id, step_index)

    try:
        result = execute_skill_task.run(skill_name=step_tpl.skill_name, **params)
        WorkflowEngine.handle_step_complete(run_id, step_index, result)
        return result
    except Exception as exc:
        logger.exception("Workflow 步骤执行异常 run=%s step=%s skill=%s", run_id, step_index, step_tpl.skill_name)
        mark_step_failed(step_rec.id, str(exc))
        WorkflowEngine.handle_step_complete(run_id, step_index, {"success": False, "error": str(exc)})
        raise
