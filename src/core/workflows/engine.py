"""Workflow 编排引擎。"""

from __future__ import annotations

import logging
from typing import Any

from src.core.workflows.events import publish_workflow_event
from src.core.workflows.artifacts import normalize_step_result
from src.core.workflows.repository import (
    create_notification,
    create_workflow_run,
    create_workflow_steps,
    get_workflow_run,
    list_workflow_steps,
    mark_step_completed,
    mark_step_failed,
    mark_step_running,
    update_run_status,
    update_run_step_index,
)
from src.core.workflows.templates import TEMPLATES, WorkflowTemplate

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
        template = TEMPLATES.get(template_name)
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
        steps = [
            {"name": s.name, "skill_name": s.skill_name, "celery_task": s.celery_task}
            for s in template.steps
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
        async_result = dispatch_workflow_step_task.apply_async(
            args=[run_id, step_index],
        )
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
        steps = list_workflow_steps(run_id)
        artifacts: dict[str, Any] = {}
        for s in steps:
            if s.output_artifacts:
                artifacts.update(s.output_artifacts)

        excel = artifacts.get("change_excel") or {}
        zip_art = artifacts.get("config_zip") or {}
        publish_workflow_event(
            run_id,
            status="completed",
            message="ITSM 变更流程已完成",
            extra={"change_excel_url": excel.get("download_url"), "config_zip_url": zip_art.get("download_url")},
        )
        cls._notify_success(run_id, excel.get("download_url"), zip_art.get("download_url"))

    @classmethod
    def _notify_success(cls, run_id: str, excel_url: str | None, zip_url: str | None) -> None:
        run = get_workflow_run(run_id)
        if not run or not run.user_id:
            return
        body = "防火墙策略与变更工单已生成。"
        if excel_url:
            body += f"\n变更工单: {excel_url}"
        create_notification(
            user_id=run.user_id,
            title=f"变更工单已完成 ({run.ticket_id or run_id[:8]})",
            body=body,
            workflow_run_id=run_id,
            thread_id=run.thread_id,
            payload={"change_excel_url": excel_url, "config_zip_url": zip_url},
            level="success",
        )

    @classmethod
    def _notify_failure(cls, run_id: str, error: str) -> None:
        run = get_workflow_run(run_id)
        if not run or not run.user_id:
            return
        create_notification(
            user_id=run.user_id,
            title=f"变更流程失败 ({run.ticket_id or run_id[:8]})",
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
        ctx = dict(run.context or {})
        ctx["workflow_run_id"] = run_id
        steps = list_workflow_steps(run_id)
        step = steps[step_index]
        template = TEMPLATES.get(run.template_name)
        if not template:
            return ctx

        step_tpl = template.steps[step_index]
        if step_tpl.skill_name == "firewall-policy-generator":
            return {
                "ticket_id": ctx.get("ticket_id"),
                "ticket_title": ctx.get("ticket_title", "防火墙策略生成"),
                "policy_file_url": ctx.get("policy_file_url"),
                "topology_file_url": ctx.get("topology_file_url"),
                "requester": ctx.get("requester", ""),
                "assignee": ctx.get("assignee", ""),
                "priority": ctx.get("priority", "P2"),
                "parameters": ctx.get("parameters"),
                "change_background": ctx.get("change_background", ""),
                "change_purpose": ctx.get("change_purpose", ""),
                "requester_dept": ctx.get("requester_dept", ""),
                "due_date": ctx.get("due_date"),
                "workflow_run_id": run_id,
            }

        prev_artifacts: dict[str, Any] = {}
        prev_manifest = None
        for i in range(step_index):
            prev = steps[i]
            if prev.output_artifacts:
                prev_artifacts.update(prev.output_artifacts)
            if prev.result and prev.result.get("manifest"):
                prev_manifest = prev.result.get("manifest")

        if step_tpl.skill_name == "itsm-change-ticket-writer":
            zip_art = prev_artifacts.get("config_zip") or {}
            return {
                "ticket_id": ctx.get("ticket_id"),
                "ticket_title": ctx.get("ticket_title", ""),
                "change_background": ctx.get("change_background", ""),
                "change_purpose": ctx.get("change_purpose", ""),
                "requester": ctx.get("requester", ""),
                "requester_dept": ctx.get("requester_dept", ""),
                "priority": ctx.get("priority", "P2"),
                "due_date": ctx.get("due_date"),
                "config_file_key": zip_art.get("file_key"),
                "config_files_url": zip_art.get("download_url"),
                "manifest": prev_manifest or (prev_artifacts.get("manifest") if prev_artifacts else None),
                "workflow_run_id": run_id,
            }

        if step_tpl.skill_name == "itsm-callback":
            excel_art = prev_artifacts.get("change_excel") or {}
            zip_art = prev_artifacts.get("config_zip") or {}
            return {
                "ticket_id": ctx.get("ticket_id"),
                "callback_url": ctx.get("callback_url"),
                "callback_headers": ctx.get("callback_headers"),
                "change_excel_url": excel_art.get("download_url"),
                "change_excel_file_key": excel_art.get("file_key"),
                "config_files_url": zip_art.get("download_url"),
                "config_file_key": zip_art.get("file_key"),
                "workflow_run_id": run_id,
            }

        return ctx
