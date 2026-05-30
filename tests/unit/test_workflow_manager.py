"""Workflow 管理器与 API 单元测试。"""

import yaml

from src.core.workflows.manager import (
    generate_from_collab_template,
    list_collab_templates,
    preview_chat_intent,
    validate_workflow_yaml,
)
from src.core.workflows.registry import get_template, load_workflows


def test_list_collab_templates_has_mode_a():
    templates = list_collab_templates()
    ids = {t["id"] for t in templates}
    assert "mode-a-firewall-llm" in ids


def test_generate_mode_a_template():
    files = generate_from_collab_template("mode-a-firewall-llm", plugin_name="test-llm-wf")
    assert files is not None
    assert "WORKFLOW.yaml" in files
    assert "llm-result-analyzer" in files["WORKFLOW.yaml"]
    assert "CHAT.intent.yaml" in files
    raw = yaml.safe_load(files["WORKFLOW.yaml"])
    assert raw["name"] == "test-llm-wf"
    assert len(raw["steps"]) == 3
    assert raw["steps"][-1]["skill"] == "llm-result-analyzer"


def test_load_firewall_llm_analysis_plugin():
    load_workflows(force=True)
    tpl = get_template("itsm-firewall-llm-analysis")
    assert tpl is not None
    assert len(tpl.steps) == 3
    assert tpl.steps[-1].skill_name == "llm-result-analyzer"


def test_validate_workflow_yaml_ok():
    files = generate_from_collab_template("mode-a-firewall-llm")
    result = validate_workflow_yaml(files["WORKFLOW.yaml"])
    assert result["valid"] is True
    assert not result["errors"]


def test_preview_chat_intent_matched():
    files = generate_from_collab_template("mode-a-firewall-llm", plugin_name="itsm-firewall-llm-analysis")
    query = "根据工单 REQ2025001 生成防火墙策略并进行 LLM 分析"
    result = preview_chat_intent(query, chat_intent_yaml=files["CHAT.intent.yaml"])
    assert result["matched"] is True
    assert result.get("ticket_id")


def test_preview_chat_intent_missing_ticket():
    files = generate_from_collab_template("mode-a-firewall-llm")
    result = preview_chat_intent("生成防火墙策略并进行 LLM 分析", chat_intent_yaml=files["CHAT.intent.yaml"])
    assert result["matched"] is False
    assert "工单" in (result.get("reason") or "")
