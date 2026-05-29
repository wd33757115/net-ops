"""Workflow 查询 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.core.workflows.repository import get_workflow_run, list_workflow_steps
from src.gateway.schemas import WorkflowRunResponse, WorkflowStepResponse

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow(run_id: str):
    run = get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow 不存在")
    steps = list_workflow_steps(run_id)
    return WorkflowRunResponse(
        run_id=run.id,
        template_name=run.template_name,
        ticket_id=run.ticket_id,
        source=run.source,
        status=run.status,
        current_step_index=run.current_step_index,
        error_message=run.error_message,
        context=run.context,
        steps=[
            WorkflowStepResponse(
                step_index=s.step_index,
                step_name=s.step_name,
                skill_name=s.skill_name,
                status=s.status,
                celery_task_id=s.celery_task_id,
                output_artifacts=s.output_artifacts,
                error_message=s.error_message,
            )
            for s in steps
        ],
        created_at=run.created_at,
        completed_at=run.completed_at,
    )
