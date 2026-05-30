"""Workflow 编排引擎。"""

from __future__ import annotations

import logging
from typing import Any

from src.core.workflows.artifacts import normalize_step_result
from src.core.workflows.events import publish_workflow_event
from src.core.workflows.expression import build_step_env, resolve_inputs, resolve_value
from src.core.workflows.registry import TEMPLATES, get_template, load_workflows, resolve_active_steps
from src.core.workflows.repository import (
    create_notification,
    create_workflow_run,
    create_workflow_steps,
    get_workflow_run,
    list_workflow_steps,
    mark_step_completed,
    mark_step_running,
    update_run_status,
    update_run_step_index,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    @classmethod
    def start(
        cls,
        template_name: str,
        context: dict[str, Any],
        *,
        source: str = "chat",
        user_id: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        load_workflows()
        template = get_template(template_name)
        if not template:
            raise ValueError(f"未知 Workflow 模板: {template_name}")

        ticket_id = context.get("ticket_id")
        run_id = create_workflow_run(
            template_name=template_name,
            context=context,
            ticket_id=ticket_id,
            source=source,
            user_id=user_id,
            thread_id=thread_id,
        )
        active_tpl_steps = resolve_active_steps(template, context, run_id=run_id)
        if not active_tpl_steps:
            raise ValueError(f"Workflow {template_name} 无可用步骤")
        steps = [
            {
                "name": s.name,
                "skill_name": s.skill_name,
                "celery_task": "execute_skill_task",
            }
            for s in active_tpl_steps
        ]
        create_workflow_steps(run_id, steps)
        update_run_status(run_id, "running")
        publish_workflow_event(
            run_id,
            status="started",
            message=f"Workflow {template_name} 已启动",
        )
        cls.dispatch_step(run_id, 0)
        return run_id

    @classmethod
    def dispatch_step(cls, run_id: str, step_index: int) -> None:
        from src.core.workflows.tasks import dispatch_workflow_step_task

        run = get_workflow_run(run_id)
        if not run:
            return
        steps = list_workflow_steps(run_id)
        if step_index >= len(steps):
            cls._complete_workflow(run_id)
            return
        update_run_step_index(run_id, step_index)
        step = steps[step_index]
        publish_workflow_event(
            run_id,
            step_name=step.step_name,
            skill_name=step.skill_name,
            status="running",
            message=f"正在执行: {step.skill_name}",
        )
        async_result = dispatch_workflow_step_task.apply_async(args=[run_id, step_index])
        mark_step_running(step.id, async_result.id)

    @classmethod
    def handle_step_complete(cls, run_id: str, step_index: int, raw_result: dict[str, Any] | None) -> None:
        steps = list_workflow_steps(run_id)
        if step_index >= len(steps):
            return
        step = steps[step_index]
        result = normalize_step_result(raw_result or {})
        mark_step_completed(step.id, result)

        if not result.get("success"):
            err = result.get("error") or result.get("message") or "步骤执行失败"
            update_run_status(run_id, "failed", error=str(err))
            publish_workflow_event(
                run_id,
                step_name=step.step_name,
                skill_name=step.skill_name,
                status="failed",
                message=str(err),
            )
            cls._notify_failure(run_id, str(err))
            return

        publish_workflow_event(
            run_id,
            step_name=step.step_name,
            skill_name=step.skill_name,
            status="completed",
            message=result.get("message") or "步骤完成",
        )

        next_index = step_index + 1
        if next_index < len(steps):
            cls.dispatch_step(run_id, next_index)
        else:
            cls._complete_workflow(run_id)

    @classmethod
    def _complete_workflow(cls, run_id: str) -> None:
        run = get_workflow_run(run_id)
        if not run:
            return
        update_run_status(run_id, "completed")
        template = get_template(run.template_name)
        steps = list_workflow_steps(run_id)
        artifacts: dict[str, Any] = {}
        for s in steps:
            if s.output_artifacts:
                artifacts.update(s.output_artifacts)

        oc = template.on_complete if template else None
        message = oc.message if oc else "Workflow 已完成"
        env = build_step_env(
            context=run.context or {},
            run_id=run_id,
            ticket_id=run.ticket_id,
            step_records=steps,
            current_step_index=len(steps),
        )
        publish_workflow_event(
            run_id,
            status="completed",
            message=message,
            extra={
                "change_excel_url": (artifacts.get("change_excel") or {}).get("download_url"),
                "config_zip_url": (artifacts.get("config_zip") or {}).get("download_url"),
            },
        )
        cls._notify_success(run_id, template, env, artifacts)

    @classmethod
    def _notify_success(
        cls,
        run_id: str,
        template,
        env: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> None:
        run = get_workflow_run(run_id)
        if not run or not run.user_id:
            return
        oc = template.on_complete if template else None
        excel = artifacts.get("change_excel") or {}
        zip_art = artifacts.get("config_zip") or {}
        title_tpl = oc.notification_title if oc else "Workflow 已完成 (${context.ticket_id})"
        body_tpl = oc.notification_body if oc else "流程已完成。"
        title = str(resolve_value(title_tpl, env) if title_tpl else "Workflow 已完成")
        body = str(resolve_value(body_tpl, env) if body_tpl else "流程已完成。")
        if excel.get("download_url"):
            body += f"\n变更工单: {excel['download_url']}"
        create_notification(
            user_id=run.user_id,
            title=title,
            body=body,
            workflow_run_id=run_id,
            thread_id=run.thread_id,
            payload={"change_excel_url": excel.get("download_url"), "config_zip_url": zip_art.get("download_url")},
            level=(oc.notification_level if oc else "success"),
        )

    @classmethod
    def _notify_failure(cls, run_id: str, error: str) -> None:
        run = get_workflow_run(run_id)
        if not run or not run.user_id:
            return
        create_notification(
            user_id=run.user_id,
            title=f"Workflow 失败 ({run.ticket_id or run_id[:8]})",
            body=error,
            workflow_run_id=run_id,
            thread_id=run.thread_id,
            level="error",
        )

    @classmethod
    def build_step_params(cls, run_id: str, step_index: int) -> dict[str, Any]:
        run = get_workflow_run(run_id)
        if not run:
            return {}
        template = get_template(run.template_name)
        if not template or step_index >= len(template.steps):
            return dict(run.context or {})

        steps = list_workflow_steps(run_id)
        if step_index >= len(steps):
            return dict(run.context or {})

        step_rec = steps[step_index]
        from src.core.workflows.registry import find_step_template

        step_tpl = find_step_template(template, step_rec.step_name)
        if not step_tpl:
            return dict(run.context or {})
        env = build_step_env(
            context=dict(run.context or {}),
            run_id=run_id,
            ticket_id=run.ticket_id,
            step_records=steps,
            current_step_index=step_index,
        )
        params = resolve_inputs(step_tpl.inputs, env)
        params["workflow_run_id"] = run_id
        return params
