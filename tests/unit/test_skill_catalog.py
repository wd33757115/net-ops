"""Skill Catalog 与分级路由单元测试。"""

from unittest.mock import patch

from src.skill_system.catalog.repository import compute_content_hash
from src.skill_system.metadata import SkillMetadata
from src.skill_system.tiered_router import catalog_allowed_skills, permission_rank


def test_permission_rank():
    assert permission_rank("admin") > permission_rank("user")
    assert permission_rank("operator") > permission_rank("guest")


@patch("src.skill_system.catalog.repository.list_catalog_entries")
def test_catalog_allowed_skills_rbac(mock_list):
    mock_list.return_value = [
        {
            "skill_name": "admin-skill",
            "enabled": True,
            "deprecated": False,
            "hidden": False,
            "min_permission_level": "admin",
            "rollout_status": "stable",
            "enabled_ratio": 100,
        },
        {
            "skill_name": "user-skill",
            "enabled": True,
            "deprecated": False,
            "hidden": False,
            "min_permission_level": "user",
            "rollout_status": "stable",
            "enabled_ratio": 100,
        },
    ]
    with patch("src.common.config.get_settings") as mock_settings:
        mock_settings.return_value.SKILL_CATALOG_ENABLED = True
        allowed = catalog_allowed_skills("user")
    assert "user-skill" in allowed
    assert "admin-skill" not in allowed


def test_content_hash_stable():
    meta = SkillMetadata(
        name="test-skill",
        description="desc",
        triggers=["a"],
        domain="security",
    )
    h1 = compute_content_hash(meta)
    h2 = compute_content_hash(meta)
    assert h1 == h2
