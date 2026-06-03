# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Skill schema API 单元测试。"""

from src.skills.skill_manager import get_skill_manager


def test_get_skill_schema_firewall():
    schema = get_skill_manager().get_skill_schema("firewall-policy-generator")
    assert schema is not None
    assert schema["name"] == "firewall-policy-generator"
    input_names = {i["name"] for i in schema["inputs"]}
    assert "ticket_id" in input_names
    assert "policy_file_url" in input_names
    assert schema.get("entry_output") == "dir"


def test_get_skill_schema_llm_analyzer():
    schema = get_skill_manager().get_skill_schema("llm-result-analyzer")
    assert schema is not None
    input_names = {i["name"] for i in schema["inputs"]}
    assert "prev_result" in input_names
    assert "analysis_prompt" in input_names


def test_get_skill_schema_missing():
    assert get_skill_manager().get_skill_schema("nonexistent-skill-xyz") is None
