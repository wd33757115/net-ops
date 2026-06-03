# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""ITSM Workflow 上下文构建。"""

from __future__ import annotations

from typing import Any

from src.gateway.schemas import ITSMFirewallPolicyRequest


def build_itsm_workflow_context(request: ITSMFirewallPolicyRequest) -> dict[str, Any]:
  return {
    "ticket_id": request.ticket_id,
    "ticket_title": request.ticket_title,
    "change_background": request.ticket_title,
    "change_purpose": request.service_catalog or "防火墙策略开通",
    "requester": request.requester,
    "requester_dept": request.requester_dept or "",
    "assignee": request.assignee or "",
    "priority": request.priority,
    "due_date": request.due_date,
    "policy_file_url": request.policy_file.url,
    "topology_file_url": request.topology_file.url if request.topology_file else None,
    "parameters": request.parameters.model_dump() if request.parameters else None,
    "callback_url": request.callback_url,
    "callback_headers": request.callback_headers,
  }


def build_chat_workflow_context(state: dict[str, Any]) -> dict[str, Any]:
  messages = state.get("messages") or []
  query = messages[-1].content if messages else ""
  return {
    "ticket_id": state.get("ticket_id"),
    "ticket_title": state.get("ticket_title") or "防火墙策略变更",
    "change_background": query[:500],
    "change_purpose": "根据用户请求生成防火墙策略并编写变更工单",
    "policy_file_url": state.get("uploaded_file_path"),
    "callback_url": state.get("callback_url"),
    "callback_headers": state.get("callback_headers"),
    "user_query": query,
  }
