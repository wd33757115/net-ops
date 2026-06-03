# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""SSE / Langfuse 辅助逻辑测试。"""

from src.auth.models import CurrentUser
from src.gateway.chat_stream import NODE_LABELS, VIEWER_VISIBLE_EVENTS, _should_emit, _summarize_node_update


def test_node_labels():
    assert "supervisor" in NODE_LABELS


def test_should_emit_viewer_summary_only():
    viewer = CurrentUser(user_id="3", username="viewer", role="viewer")
    assert _should_emit("final_answer", viewer) is True
    assert _should_emit("node_start", viewer) is False
    assert _should_emit("node_start", None) is True


def test_should_emit_operator_detail():
    op = CurrentUser(user_id="2", username="op", role="operator")
    assert _should_emit("skill_execute", op) is True


def test_summarize_node_update_with_next_agent():
    summary = _summarize_node_update("supervisor", {"next_agent": "knowledge_qa"})
    assert summary["node"] == "supervisor"
    assert summary["next_agent"] == "knowledge_qa"


def test_viewer_visible_events():
    assert "trace_start" in VIEWER_VISIBLE_EVENTS
    assert "node_start" not in VIEWER_VISIBLE_EVENTS
