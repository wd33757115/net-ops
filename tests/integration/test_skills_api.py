"""SkillManager 与 Skills API 集成测试。"""

import pytest

from src.skills.skill_manager import SkillManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    mgr = SkillManager()
    monkeypatch.setattr(mgr, "_skills_dir", skills_dir)
    return mgr


def test_create_save_and_upload_skill(manager):
    result = manager.create_skill(
        {
            "name": "test-skill",
            "description": "测试 Skill",
            "category": "general",
            "tags": ["test"],
            "triggers": ["run test"],
        }
    )
    assert result["success"] is True

    content = manager.get_skill_content("test-skill")
    assert content is not None
    assert "test-skill" in content

    save_result = manager.save_skill_content("test-skill", content + "\n\n## Updated")
    assert save_result["success"] is True

    upload_result = manager.upload_skill_file(
        "test-skill",
        "scripts",
        "test.py",
        "cHJpbnQoJ2hlbGxvJyk=",  # print('hello')
    )
    assert upload_result["success"] is True

    files = manager.list_skill_files("test-skill")
    assert files["success"] is True
    assert "test.py" in files["files"]["scripts"]


def test_delete_skill(manager):
    manager.create_skill(
        {"name": "delete-skill", "description": "delete", "category": "general", "triggers": ["d"]}
    )

    deleted = manager.delete_skill("delete-skill")
    assert deleted["success"] is True
    assert not (manager._skills_dir / "delete-skill").exists()
