"""SkillRunner 单元测试。"""

from unittest.mock import patch

import pytest

from src.core.skills.executor import SkillExecutionError
from src.core.skills.result import ExecutionContext, SkillStatus
from src.core.skills.runner import SkillRunner


@patch("src.core.skills.runner.finalize_skill_execution", side_effect=lambda r: r)
@patch("src.core.skills.runner.record_skill_execution_span")
@patch("src.core.skills.executor._execute_skill_impl")
def test_runner_success(mock_impl, _span, _finalize):
    mock_impl.return_value = {
        "success": True,
        "message": "完成",
        "download_url": "https://example.com/a.zip",
        "config_file_key": "firewall_policies/T1/a.zip",
        "filename": "a.zip",
    }
    ctx = ExecutionContext(source="workflow", thread_id="t1", ticket_id="T1")
    result = SkillRunner.run("firewall-policy-generator", {"ticket_id": "T1"}, context=ctx)
    assert result.status == SkillStatus.SUCCESS
    assert result.context.source == "workflow"
    assert "config_zip" in result.artifacts
    assert result.metadata.get("duration_ms") is not None


@patch("src.core.skills.runner.finalize_skill_execution", side_effect=lambda r: r)
@patch("src.core.skills.runner.record_skill_execution_span")
@patch("src.core.skills.executor._execute_skill_impl")
def test_runner_skill_error(mock_impl, _span, _finalize):
    mock_impl.side_effect = SkillExecutionError("脚本失败")
    with pytest.raises(SkillExecutionError):
        SkillRunner.run("bad-skill", {}, context=ExecutionContext(source="celery"))
