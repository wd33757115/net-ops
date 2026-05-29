"""预定义 Workflow 模板（确定性编排，不由 LLM 生成）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowStepTemplate:
    name: str
    skill_name: str
    celery_task: str


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    steps: list[WorkflowStepTemplate] = field(default_factory=list)


ITSM_FIREWALL_CHANGE = WorkflowTemplate(
    name="itsm-firewall-change",
    description="ITSM 防火墙策略开通：生成配置 ZIP → 编写变更工单 Excel → 回调 ITSM",
    steps=[
        WorkflowStepTemplate(
            name="policy_generation",
            skill_name="firewall-policy-generator",
            celery_task="execute_firewall_policy_task",
        ),
        WorkflowStepTemplate(
            name="change_ticket",
            skill_name="itsm-change-ticket-writer",
            celery_task="execute_itsm_change_ticket_task",
        ),
        WorkflowStepTemplate(
            name="itsm_callback",
            skill_name="itsm-callback",
            celery_task="execute_itsm_callback_task",
        ),
    ],
)

TEMPLATES: dict[str, WorkflowTemplate] = {
    ITSM_FIREWALL_CHANGE.name: ITSM_FIREWALL_CHANGE,
}
