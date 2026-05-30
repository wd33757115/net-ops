"""聊天意图 → Workflow 插件（扫描 **/CHAT.intent.yaml）。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.core.plugins.context_mapping import map_state_to_context
from src.core.workflows.registry import WORKFLOWS_ROOT, format_steps_flow, get_template, resolve_active_steps

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatIntentPlugin:
    workflow: str
    priority: int
    description: str
    plugin_dir: Path
    require_any: list[str] = field(default_factory=list)
    require_all: list[str] = field(default_factory=list)
    require_any_secondary: list[str] = field(default_factory=list)
    auto_sources: list[str] = field(default_factory=list)
    context_from_state: dict[str, str] = field(default_factory=dict)
    context_defaults: dict[str, Any] = field(default_factory=dict)
    response_template: str = ""


class ChatIntentRegistry:
    def __init__(self) -> None:
        self._intents: list[ChatIntentPlugin] = []

    def load(self, force: bool = False) -> None:
        if self._intents and not force:
            return
        self._intents.clear()
        if not WORKFLOWS_ROOT.is_dir():
            return
        for path in sorted(WORKFLOWS_ROOT.rglob("CHAT.intent.yaml")):
            intent = self._parse(path)
            if intent:
                self._intents.append(intent)
                logger.info("已加载 Chat Intent 插件: %s → %s", path.parent.name, intent.workflow)
        self._intents.sort(key=lambda x: -x.priority)

    def _parse(self, path: Path) -> ChatIntentPlugin | None:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("解析 CHAT.intent.yaml 失败 %s: %s", path, exc)
            return None
        workflow = raw.get("workflow")
        if not workflow:
            return None
        match = raw.get("match") or {}
        return ChatIntentPlugin(
            workflow=str(workflow),
            priority=int(raw.get("priority") or 0),
            description=str(raw.get("description") or ""),
            plugin_dir=path.parent,
            require_any=list(match.get("require_any") or []),
            require_all=list(match.get("require_all") or []),
            require_any_secondary=list(match.get("require_any_secondary") or match.get("require_any_after") or []),
            auto_sources=list(raw.get("auto_if_source") or raw.get("auto_sources") or []),
            context_from_state=dict(raw.get("context_from_state") or {}),
            context_defaults=dict(raw.get("context_defaults") or {}),
            response_template=str(raw.get("response_template") or ""),
        )

    def all_intents(self) -> list[ChatIntentPlugin]:
        self.load()
        return list(self._intents)

    def get_intent(self, workflow_name: str) -> ChatIntentPlugin | None:
        self.load()
        for intent in self._intents:
            if intent.workflow == workflow_name:
                return intent
        return None


class MissingTicketIdError(ValueError):
    """当前消息未包含可识别的工单号。"""


TICKET_REQUIRED_MSG = (
    "未在当前消息中识别到工单号。请在话术中明确工单编号，例如：\n"
    "「根据工单 REQ2025，用策略文件生成防火墙策略并编写变更工单」"
)


def _current_query(state: dict[str, Any]) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return str(last.get("content") or "")
    return str(getattr(last, "content", "") or "")


def require_ticket_id_from_query(query: str) -> str:
    """从当前用户消息提取工单号（Workflow 启动必填，不使用会话历史）。"""
    from src.common.ticket_utils import extract_ticket_id

    ticket_id = extract_ticket_id(query or "")
    if not ticket_id:
        raise MissingTicketIdError(TICKET_REQUIRED_MSG)
    return ticket_id


_registry = ChatIntentRegistry()


def _query_matches(query: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(re.search(re.escape(p), query, re.IGNORECASE) for p in patterns)


def match_chat_workflow(query: str, source: str | None) -> ChatIntentPlugin | None:
    from src.common.ticket_utils import extract_ticket_id

    _registry.load()
    for intent in _registry._intents:
        if source and source in intent.auto_sources:
            return intent
    for intent in _registry._intents:
        if intent.require_any and not _query_matches(query, intent.require_any):
            continue
        if intent.require_all and not all(
            re.search(re.escape(p), query, re.IGNORECASE) for p in intent.require_all
        ):
            continue
        if intent.require_any_secondary and not _query_matches(query, intent.require_any_secondary):
            continue
        if intent.require_any or intent.require_all or intent.require_any_secondary:
            # 聊天触发 Workflow 必须在本轮话术中识别到工单号
            if not extract_ticket_id(query or ""):
                return None
            return intent
    return None


def build_chat_workflow_context(state: dict[str, Any], intent: ChatIntentPlugin) -> dict[str, Any]:
    query = _current_query(state)
    ticket_id = require_ticket_id_from_query(query)

    ctx = dict(intent.context_defaults)
    # 工单号仅来自当前消息，禁止从 state / 历史会话映射
    state_mapping = {
        k: v for k, v in intent.context_from_state.items() if k != "ticket_id" and v != "ticket_id"
    }
    ctx.update(map_state_to_context(state, state_mapping))
    ctx["ticket_id"] = ticket_id
    if query:
        ctx.setdefault("change_background", query[:500])
    if state.get("ticket_title"):
        ctx.setdefault("ticket_title", state.get("ticket_title"))
    return ctx


def format_workflow_start_message(intent: ChatIntentPlugin, run_id: str, context: dict[str, Any]) -> str:
    tpl = get_template(intent.workflow)
    if tpl:
        active = resolve_active_steps(tpl, context, run_id=run_id)
        desc = format_steps_flow(active)
    else:
        desc = intent.workflow
    ticket = context.get("ticket_id") or "—"
    if intent.response_template:
        return intent.response_template.format(
            run_id=run_id,
            ticket_id=ticket,
            workflow_description=desc,
            workflow=intent.workflow,
        )
    return (
        f"[OK] 已启动 Workflow `{intent.workflow}`\n\n"
        f"- **流程 ID**: `{run_id}`\n"
        f"- **工单**: {ticket}\n"
        f"- **说明**: {desc}\n"
    )


def get_chat_intent_registry() -> ChatIntentRegistry:
    return _registry
