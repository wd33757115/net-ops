"""Skill 契约测试。"""

from src.core.skills.contract import assert_valid_execution_result, validate_execution_result
from src.core.skills.result import SkillExecutionResult, SkillStatus


def test_valid_success_result():
    raw = {
        "success": True,
        "message": "ok",
        "download_url": "https://minio/p.zip",
        "config_file_key": "firewall_policies/T1/p.zip",
        "filename": "p.zip",
    }
    errors = validate_execution_result(raw, skill_name="firewall-policy-generator", require_success=True)
    assert errors == []
    ser = assert_valid_execution_result(raw, skill_name="firewall-policy-generator")
    assert ser.status == SkillStatus.SUCCESS
    assert "config_zip" in ser.artifacts


def test_missing_artifact_for_download_output():
    raw = {"success": True, "message": "ok"}
    errors = validate_execution_result(raw, skill_name="firewall-policy-generator")
    assert any("config_zip" in e or "config_files" in e for e in errors)


def test_schema_version_required():
    ser = SkillExecutionResult(skill_name="x", status=SkillStatus.SUCCESS)
    assert ser.schema_version == "1"
