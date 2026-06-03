# -*- coding: utf-8 -*-
"""
测试 Skill 元数据解析
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.skill_system.metadata import (
    parse_skill_md,
    parse_frontmatter,
    SkillMetadata,
    create_skill_md
)


def test_parse_frontmatter():
    """测试 frontmatter 解析"""
    content = """---
name: test-skill
version: 1.0.0
description: 测试技能
category: test
---

这是正文内容
"""

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter["name"] == "test-skill"
    assert frontmatter["version"] == "1.0.0"
    assert frontmatter["description"] == "测试技能"
    assert body.strip() == "这是正文内容"
    print("[OK] test_parse_frontmatter")


def test_parse_frontmatter_no_yaml():
    """测试没有 frontmatter 的情况"""
    content = "这只是纯文本内容"

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {}
    assert body == content
    print("[OK] test_parse_frontmatter_no_yaml")


def test_create_skill_md():
    """测试创建 SKILL.md"""
    content = create_skill_md(
        skill_name="test-skill",
        description="测试技能描述",
        category="test",
        tags=["test", "demo"],
        triggers=["测试", "demo"]
    )

    assert "name: test-skill" in content
    assert "测试技能描述" in content
    assert "category: test" in content
    assert "rollout_status: draft" in content
    assert "domain: general" in content
    print("[OK] test_create_skill_md")


def test_skill_metadata_model():
    """测试 SkillMetadata 模型"""
    metadata = SkillMetadata(
        name="test-skill",
        version="1.0.0",
        description="测试描述",
        category="test",
        tags=["tag1", "tag2"],
        triggers=["trigger1", "trigger2"]
    )

    assert metadata.name == "test-skill"
    assert metadata.version == "1.0.0"
    assert len(metadata.tags) == 2
    assert len(metadata.triggers) == 2

    # 测试 get_llm_description
    desc = metadata.get_llm_description()
    assert "test-skill" in desc
    assert "测试描述" in desc
    print("[OK] test_skill_metadata_model")


if __name__ == "__main__":
    print("=" * 50)
    print("运行 Skill 元数据测试")
    print("=" * 50)

    test_parse_frontmatter()
    test_parse_frontmatter_no_yaml()
    test_create_skill_md()
    test_skill_metadata_model()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)
