# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""LLM 结果分析 Skill 单元测试（不调用真实 LLM）。"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "src" / "skills" / "llm-result-analyzer" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from llm_analyze import build_input_summary, load_upstream_payload  # noqa: E402


def test_load_upstream_from_prev_result():
    params = {"prev_result": {"success": True, "manifest": {"ticket_id": "T1"}}}
    up = load_upstream_payload(params)
    assert up["manifest"]["ticket_id"] == "T1"


def test_build_summary_includes_manifest():
    upstream = {"success": True, "message": "ok", "manifest": {"devices": [{"name": "fw1"}]}}
    text = build_input_summary(upstream, {"ticket_id": "REQ1"})
    assert "REQ1" in text
    assert "fw1" in text
