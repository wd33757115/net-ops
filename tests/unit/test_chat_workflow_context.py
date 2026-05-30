"""聊天 Workflow 上下文：工单号必须来自当前消息。"""

import pytest

from src.core.plugins.chat_intent import (
    ChatIntentPlugin,
    MissingTicketIdError,
    build_chat_workflow_context,
    require_ticket_id_from_query,
)
from pathlib import Path


def _firewall_intent() -> ChatIntentPlugin:
    return ChatIntentPlugin(
        workflow="itsm-firewall-change",
        priority=100,
        description="test",
        plugin_dir=Path("."),
        context_from_state={"ticket_id": "ticket_id", "policy_file_url": "uploaded_file_path"},
        context_defaults={"change_purpose": "默认目的"},
    )


def test_require_ticket_from_current_message():
    assert require_ticket_id_from_query("根据工单REQ2025，生成变更工单") == "REQ2025"


def test_require_ticket_raises_without_id():
    with pytest.raises(MissingTicketIdError):
        require_ticket_id_from_query("请生成防火墙策略")


def test_build_context_ignores_stale_state_ticket():
    state = {
        "ticket_id": "test001",
        "uploaded_file_path": "/tmp/policy.xlsx",
        "messages": [{"content": "根据工单REQ2025，编写变更工单"}],
    }
    ctx = build_chat_workflow_context(state, _firewall_intent())
    assert ctx["ticket_id"] == "REQ2025"
    assert ctx["policy_file_url"] == "/tmp/policy.xlsx"
