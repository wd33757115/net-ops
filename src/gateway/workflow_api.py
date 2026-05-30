"""Workflow 查询与管理 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.workflows.engine import WorkflowEngine
from src.core.workflows.manager import (
    generate_from_collab_template,
    get_plugin_detail,
    list_collab_templates,
    preview_chat_intent,
    save_plugin,
    template_to_summary,
    validate_plugin_files,
    validate_workflow_yaml,
)
from src.core.workflows.registry import get_template, list_templates, load_workflows
from src.core.workflows.repository import get_workflow_run, list_workflow_runs, list_workflow_steps
from src.gateway.schemas import WorkflowRunResponse, WorkflowStepResponse

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


class ValidateWorkflowRequest(BaseModel):
    workflow_yaml: str = Field(..., description="WORKFLOW.yaml 内容")
    chat_intent_yaml: str | None = None


class SaveWorkflowPluginRequest(BaseModel):
    name: str = Field(..., description="插件目录名")
    category: str = Field(default="itsm", description="workflows 下子目录")
    files: dict[str, str] = Field(..., description="WORKFLOW.yaml / CHAT.intent.yaml 等")


class ChatIntentPreviewRequest(BaseModel):
    query: str = Field(..., description="测试话术")
    workflow_name: str | None = None
    chat_intent_yaml: str | None = None
    context: dict[str, Any] | None = None


class WorkflowTestRunRequest(BaseModel):
    template_name: str
    context: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    thread_id: str | None = None


class GenerateTemplateRequest(BaseModel):
    template_id: str
    plugin_name: str | None = None
    step1_skill: str = "firewall-policy-generator"
    step2_skill: str = "itsm-change-ticket-writer"
    description: str | None = None


def _run_to_response(run) -> WorkflowRunResponse:
    steps = list_workflow_steps(run.id)
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


@router.get("/templates")
async def list_workflow_templates():
    load_workflows(force=True)
    return [template_to_summary(t) for t in list_templates()]


@router.get("/collab-templates")
async def get_collab_templates():
    return list_collab_templates()


@router.post("/collab-templates/generate")
async def generate_collab_template(request: GenerateTemplateRequest):
    files = generate_from_collab_template(
        request.template_id,
        plugin_name=request.plugin_name,
        step1_skill=request.step1_skill,
        step2_skill=request.step2_skill,
        description=request.description,
    )
    if not files:
        raise HTTPException(status_code=404, detail="未知协同模板")
    return {"files": files}


@router.get("/templates/{name}")
async def get_workflow_template(name: str):
    detail = get_plugin_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Workflow 模板 '{name}' 不存在")
    return detail


@router.post("/reload")
async def reload_workflows():
    load_workflows(force=True)
    from src.core.plugins.chat_intent import get_chat_intent_registry
    from src.core.plugins.itsm_webhook import get_itsm_webhook_registry

    get_chat_intent_registry().load(force=True)
    get_itsm_webhook_registry().load(force=True)
    return {"success": True, "count": len(list_templates()), "message": "Workflow 插件已重载"}


@router.post("/validate")
async def validate_workflow(request: ValidateWorkflowRequest):
    if request.chat_intent_yaml:
        return validate_plugin_files(
            {"WORKFLOW.yaml": request.workflow_yaml, "CHAT.intent.yaml": request.chat_intent_yaml}
        )
    return validate_workflow_yaml(request.workflow_yaml)


@router.post("/templates", status_code=201)
async def create_workflow_plugin(request: SaveWorkflowPluginRequest):
    result = save_plugin(request.name, category=request.category, files=request.files)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "保存失败"))
    return result


@router.put("/templates/{name}")
async def update_workflow_plugin(name: str, request: SaveWorkflowPluginRequest):
    tpl = get_template(name)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Workflow 模板 '{name}' 不存在")
    category = request.category or tpl.plugin_dir.parent.name
    result = save_plugin(name, category=category, files=request.files)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "保存失败"))
    return result


@router.post("/chat-intent/preview")
async def preview_chat_intent_match(request: ChatIntentPreviewRequest):
    return preview_chat_intent(
        request.query,
        workflow_name=request.workflow_name,
        chat_intent_yaml=request.chat_intent_yaml,
        context=request.context,
    )


@router.get("/runs")
async def list_runs(limit: int = 50, template_name: str | None = None, ticket_id: str | None = None):
    runs = list_workflow_runs(limit=limit, template_name=template_name, ticket_id=ticket_id)
    return [
        {
            "run_id": r.id,
            "template_name": r.template_name,
            "ticket_id": r.ticket_id,
            "source": r.source,
            "status": r.status,
            "current_step_index": r.current_step_index,
            "error_message": r.error_message,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
        }
        for r in runs
    ]


@router.post("/runs/test")
async def test_run_workflow(request: WorkflowTestRunRequest):
    tpl = get_template(request.template_name)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"未知 Workflow: {request.template_name}")
    ctx = dict(request.context)
    if not ctx.get("ticket_id"):
        raise HTTPException(status_code=400, detail="context.ticket_id 必填")
    try:
        run_id = WorkflowEngine.start(
            request.template_name,
            ctx,
            source="test",
            user_id=request.user_id,
            thread_id=request.thread_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = get_workflow_run(run_id)
    return {
        "success": True,
        "run_id": run_id,
        "message": f"已启动试跑 Workflow `{request.template_name}`",
        "query_endpoint": f"/api/v1/workflows/{run_id}",
        "run": _run_to_response(run) if run else None,
    }


@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow(run_id: str):
    run = get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow 不存在")
    return _run_to_response(run)
