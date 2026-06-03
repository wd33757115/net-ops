# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Supervisor v2 SSE 流式聊天 + Langfuse trace 事件。"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, AsyncIterator

from fastapi import Request

from src.auth.models import CurrentUser
from src.core.logging import bind_context, get_logger, reset_context
from src.gateway.audit_service import write_audit_log
from src.gateway.chat_context import prepare_chat, validate_chat_user
from src.gateway.conversation_service import get_conversation_service
from src.gateway.diagnostics import extract_download_url_from_graph_result
from src.gateway.schemas import ChatRequest, ChatResponse
from src.observability.langfuse import (
    LangfuseChatTrace,
    end_chat_trace,
    get_trace_url,
    is_langfuse_enabled,
    record_graph_node,
    start_chat_trace,
)

log = get_logger(__name__)

NODE_LABELS: dict[str, str] = {
    "pre_process": "Skill 匹配与指令加载",
    "supervisor": "Supervisor 规划",
    "orchestrator": "编排调度",
    "skill_executor_v2": "Skill 执行",
    "workflow_starter": "ITSM 变更流程启动",
    "final_aggregator": "结果聚合",
    "knowledge_qa": "知识库问答",
}

VIEWER_VISIBLE_EVENTS = frozenset({"trace_start", "status", "final_answer", "error"})


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _summarize_node_update(node: str, update: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"node": node, "label": NODE_LABELS.get(node, node)}
    if plan := update.get("execution_plan"):
        skills = [s.skill_name for s in getattr(plan, "skills", []) or []]
        summary["skills"] = skills
        summary["execution_mode"] = getattr(plan, "execution_mode", None)
    if next_agent := update.get("next_agent"):
        summary["next_agent"] = next_agent
    if skill_decision := update.get("skill_decision"):
        summary["skill"] = getattr(skill_decision, "skill_name", None)
    if intermediate := update.get("intermediate_results"):
        summary["completed_skills"] = list(intermediate.keys()) if isinstance(intermediate, dict) else []
    return summary


def _should_emit(event: str, user: CurrentUser | None) -> bool:
    if not user or user.can_view_trace_detail():
        return True
    return event in VIEWER_VISIBLE_EVENTS


async def stream_supervisor_chat(
    *,
    request: ChatRequest,
    http_request: Request,
    user: CurrentUser | None,
    agent_graph,
    enforce_auth: bool,
) -> AsyncIterator[dict[str, str]]:
    validate_chat_user(user, enforce_auth=enforce_auth)

    prepared = prepare_chat(request, user)
    stream_started = time.monotonic()
    context_tokens = bind_context(
        thread_id=prepared.graph_thread_id,
        user_id=prepared.effective_user_id,
        ticket_id=request.ticket_id,
    )
    lf_trace: LangfuseChatTrace | None = start_chat_trace(
        user=user,
        thread_id=prepared.graph_thread_id,
        conversation_id=prepared.conversation_id,
        trace_name="supervisor_v2_stream",
        query=request.query,
    )

    trace_id = lf_trace.trace_id if lf_trace else None
    if trace_id:
        context_tokens.extend(bind_context(trace_id=trace_id))
        prepared.initial_state["langfuse_parent_trace_id"] = trace_id
    graph_timeout = int(os.getenv("CHAT_GRAPH_TIMEOUT", "170"))
    conv_service = get_conversation_service()
    final_result: dict[str, Any] = {}

    log.info(
        "chat_stream_started",
        conversation_id=prepared.conversation_id,
        query_len=len(request.query or ""),
        trace_id=trace_id,
    )

    if _should_emit("trace_start", user):
        yield _sse(
            "trace_start",
            {
                "conversation_id": prepared.conversation_id,
                "thread_id": prepared.graph_thread_id,
                "trace_id": trace_id,
                "langfuse_enabled": is_langfuse_enabled(),
                "langfuse_url": get_trace_url(trace_id) if user and user.is_admin() else None,
            },
        )

    if _should_emit("status", user):
        yield _sse("status", {"status": "running", "message": "Agent 开始执行..."})

    deadline = time.monotonic() + graph_timeout

    try:
        async for chunk in agent_graph.astream(
            prepared.initial_state,
            prepared.config,
            stream_mode="updates",
        ):
            if time.monotonic() > deadline:
                raise asyncio.TimeoutError()
            if not isinstance(chunk, dict):
                continue
            for node_name, update in chunk.items():
                if not isinstance(update, dict):
                    update = {}
                summary = _summarize_node_update(node_name, update)
                record_graph_node(lf_trace, node_name, summary)
                if node_name == "skill_executor_v2" and _should_emit("skill_execute", user):
                    yield _sse("skill_execute", {**summary, "status": "running"})
                elif _should_emit("node_start", user):
                    yield _sse("node_start", {**summary, "status": "completed"})
                if _should_emit("trace_update", user):
                    yield _sse(
                        "trace_update",
                        {"node": node_name, "trace_id": trace_id, "progress": summary},
                    )

        state_snapshot = await asyncio.to_thread(agent_graph.get_state, prepared.config)
        final_result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - stream_started) * 1000)
        log.warning(
            "chat_stream_timeout",
            duration_ms=duration_ms,
            timeout_seconds=graph_timeout,
            trace_id=trace_id,
        )
        end_chat_trace(lf_trace, error=f"Agent 处理超时（{graph_timeout}秒）")
        yield _sse("error", {"message": f"Agent 处理超时（{graph_timeout}秒）", "trace_id": trace_id})
        reset_context(context_tokens)
        return
    except Exception as exc:
        duration_ms = int((time.monotonic() - stream_started) * 1000)
        log.error(
            "chat_stream_failed",
            duration_ms=duration_ms,
            error=str(exc),
            trace_id=trace_id,
            exc_info=exc,
        )
        end_chat_trace(lf_trace, error=str(exc))
        yield _sse("error", {"message": str(exc), "trace_id": trace_id})
        reset_context(context_tokens)
        return

    messages = final_result.get("messages") or []
    if not messages:
        duration_ms = int((time.monotonic() - stream_started) * 1000)
        log.warning("chat_stream_empty_result", duration_ms=duration_ms, trace_id=trace_id)
        end_chat_trace(lf_trace, error="未获得 Agent 结果")
        yield _sse("error", {"message": "未获得 Agent 结果", "trace_id": trace_id})
        reset_context(context_tokens)
        return

    response_msg = messages[-1].content
    if isinstance(response_msg, list):
        response_msg = str(response_msg)

    next_agent = final_result.get("next_agent")
    references = final_result.get("knowledge_references")
    celery_task_id = final_result.get("celery_task_id")
    download_url = extract_download_url_from_graph_result(final_result)

    end_chat_trace(
        lf_trace,
        output={
            "response": response_msg,
            "agent_type": next_agent,
            "celery_task_id": celery_task_id,
        },
    )

    conv_service.add_message(conversation_id=prepared.conversation_id, role="user", content=request.query)
    conv_service.add_message(
        conversation_id=prepared.conversation_id,
        role="assistant",
        content=response_msg,
        agent_type=next_agent,
        celery_task_id=celery_task_id,
        download_url=download_url,
        references=references,
    )
    title = conv_service.generate_title(prepared.conversation_id)
    conv_service.update_conversation(prepared.conversation_id, title=title)

    write_audit_log(
        action="chat_stream",
        user_id=prepared.effective_user_id,
        username=user.username if user else None,
        resource_type="conversation",
        resource_id=prepared.conversation_id,
        detail={
            "agent_type": next_agent,
            "query_len": len(request.query or ""),
            "trace_id": trace_id,
            "graph_thread_id": prepared.graph_thread_id,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    payload = ChatResponse(
        response=response_msg,
        thread_id=prepared.conversation_id,
        agent_type=next_agent,
        task_id=final_result.get("task_id"),
        celery_task_id=celery_task_id,
        download_url=download_url,
        references=references,
    ).model_dump()

    workflow_run_id = final_result.get("workflow_run_id")
    duration_ms = int((time.monotonic() - stream_started) * 1000)
    log.info(
        "chat_stream_finished",
        duration_ms=duration_ms,
        next_agent=next_agent,
        workflow_run_id=workflow_run_id,
        celery_task_id=celery_task_id,
        trace_id=trace_id,
    )

    if _should_emit("final_answer", user):
        yield _sse(
            "final_answer",
            {
                **payload,
                "trace_id": trace_id,
                "workflow_run_id": workflow_run_id,
                "langfuse_url": get_trace_url(trace_id) if user and user.is_admin() else None,
            },
        )
    reset_context(context_tokens)
