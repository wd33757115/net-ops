"""扫描加载 Workflow 插件包（src/workflows/**/WORKFLOW.yaml）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_ROOT = PROJECT_ROOT / "src" / "workflows"


@dataclass(frozen=True)
class WorkflowStepTemplate:
    name: str
    skill_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    when: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class WorkflowCompletionConfig:
    message: str = "Workflow 已完成"
    notification_title: str | None = None
    notification_body: str | None = None
    notification_level: str = "success"


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    version: str
    steps: list[WorkflowStepTemplate]
    plugin_dir: Path
    on_complete: WorkflowCompletionConfig = field(default_factory=WorkflowCompletionConfig)


_TEMPLATES: dict[str, WorkflowTemplate] = {}


def _parse_workflow_file(path: Path) -> WorkflowTemplate | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("解析 Workflow 失败 %s: %s", path, exc)
        return None

    name = raw.get("name")
    if not name:
        logger.warning("WORKFLOW.yaml 缺少 name: %s", path)
        return None

    steps: list[WorkflowStepTemplate] = []
    for item in raw.get("steps") or []:
        skill = item.get("skill") or item.get("skill_name")
        if not item.get("name") or not skill:
            continue
        steps.append(
            WorkflowStepTemplate(
                name=str(item["name"]),
                skill_name=str(skill),
                inputs=dict(item.get("inputs") or {}),
                when=item.get("when"),
                label=item.get("label"),
            )
        )

    oc = raw.get("on_complete") or {}
    notif = oc.get("notification") or {}
    on_complete = WorkflowCompletionConfig(
        message=str(oc.get("message") or "Workflow 已完成"),
        notification_title=notif.get("title"),
        notification_body=notif.get("body"),
        notification_level=str(notif.get("level") or "success"),
    )

    return WorkflowTemplate(
        name=str(name),
        description=str(raw.get("description") or ""),
        version=str(raw.get("version") or "1.0"),
        steps=steps,
        plugin_dir=path.parent,
        on_complete=on_complete,
    )


def load_workflows(force: bool = False) -> dict[str, WorkflowTemplate]:
    global _TEMPLATES
    if _TEMPLATES and not force:
        return _TEMPLATES

    found: dict[str, WorkflowTemplate] = {}
    if WORKFLOWS_ROOT.is_dir():
        for path in sorted(WORKFLOWS_ROOT.rglob("WORKFLOW.yaml")):
            tpl = _parse_workflow_file(path)
            if tpl:
                found[tpl.name] = tpl
                logger.info("已加载 Workflow 插件: %s (%s)", tpl.name, path.parent)

    _TEMPLATES = found
    return _TEMPLATES


def get_template(name: str) -> WorkflowTemplate | None:
    load_workflows()
    return _TEMPLATES.get(name)


def list_templates() -> list[WorkflowTemplate]:
    load_workflows()
    return list(_TEMPLATES.values())


def find_step_template(template: WorkflowTemplate, step_name: str) -> WorkflowStepTemplate | None:
    for step in template.steps:
        if step.name == step_name:
            return step
    return None


def resolve_active_steps(
    template: WorkflowTemplate,
    context: dict[str, Any],
    *,
    run_id: str = "pending",
) -> list[WorkflowStepTemplate]:
    """按 context 解析 when 条件，返回本次实际执行的步骤。"""
    from src.core.workflows.expression import build_step_env, step_is_enabled

    env = build_step_env(
        context=context,
        run_id=run_id,
        ticket_id=context.get("ticket_id"),
        step_records=[],
        current_step_index=0,
    )
    return [s for s in template.steps if step_is_enabled(s.when, env)]


def format_steps_flow(steps: list[WorkflowStepTemplate]) -> str:
    labels = [s.label or s.name for s in steps]
    return " → ".join(labels) if labels else "（无步骤）"


# 模块导入时加载
TEMPLATES: dict[str, WorkflowTemplate] = load_workflows()
