# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""
测试 Skill 加载器（Progressive Disclosure）
"""
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.skill_system.loader import SkillLoader, SkillContent, load_skill_instructions
from src.skill_system.metadata import SkillMetadata


def _create_temp_skill_dir(content: str = None):
    """创建临时 Skill 目录"""
    if content is None:
        content = """---
name: test-skill
version: 1.0.0
description: 测试技能
category: test
tags: [test, demo]
triggers:
  - "测试触发词"
  - "demo trigger"
inputs:
  - name: param1
    type: string
    required: true
    description: 参数1
outputs:
  - name: result
    type: text
    description: 输出结果
enabled: true
fallback_to_rag: true
---

# 测试技能

这是测试技能的核心指令。

## 工作流程

1. 接收参数
2. 执行任务
3. 返回结果
"""
    tmpdir = tempfile.mkdtemp()
    skill_dir = Path(tmpdir) / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir.parent, skill_dir


def test_scan_skill_dirs():
    """测试扫描 Skill 目录"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    assert "test-skill" in loader._metadata_cache
    metadata = loader._metadata_cache["test-skill"]
    assert metadata.name == "test-skill"
    assert metadata.version == "1.0.0"
    assert metadata.description == "测试技能"
    assert metadata.category == "test"
    assert len(metadata.tags) == 2

    print("[OK] test_scan_skill_dirs")


def test_get_metadata():
    """测试获取 Skill 元数据"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    metadata = loader.get_metadata("test-skill")
    assert metadata is not None
    assert metadata.name == "test-skill"
    assert metadata.enabled is True
    assert metadata.fallback_to_rag is True

    print("[OK] test_get_metadata")


def test_get_metadata_not_found():
    """测试获取不存在的 Skill 元数据"""
    loader = SkillLoader()
    metadata = loader.get_metadata("non-existent")
    assert metadata is None
    print("[OK] test_get_metadata_not_found")


def test_get_skill_content():
    """测试获取 Skill 指令内容（Progressive Disclosure）"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    content = loader.get_skill_content("test-skill")
    assert content is not None
    assert len(content) > 0
    assert "测试技能的核心指令" in content
    assert "工作流程" in content

    print("[OK] test_get_skill_content")


def test_get_skill_content_cached():
    """测试 Skill 内容缓存"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    content1 = loader.get_skill_content("test-skill")
    content2 = loader.get_skill_content("test-skill")

    assert content1 == content2
    assert "test-skill" in loader._content_cache

    print("[OK] test_get_skill_content_cached")


def test_get_skill_content_not_found():
    """测试获取不存在的 Skill 内容"""
    loader = SkillLoader()
    content = loader.get_skill_content("non-existent")
    assert content == ""
    print("[OK] test_get_skill_content_not_found")


def test_list_all_metadata():
    """测试列出所有 Skill 元数据"""
    content1 = """---
name: skill-a
version: 1.0.0
description: Skill A
category: test
tags: [a]
triggers: ["触发A"]
enabled: true
---

# Skill A
"""
    content2 = """---
name: skill-b
version: 1.0.0
description: Skill B
category: test
tags: [b]
triggers: ["触发B"]
enabled: true
---

# Skill B
"""
    tmpdir = tempfile.mkdtemp()
    for name, content in [("skill-a", content1), ("skill-b", content2)]:
        d = Path(tmpdir) / name
        d.mkdir()
        (d / "SKILL.md").write_text(content, encoding="utf-8")

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    skills = loader.list_all_metadata()
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert "skill-a" in names
    assert "skill-b" in names

    print("[OK] test_list_all_metadata")


def test_reload_skill():
    """测试重新加载 Skill"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    content1 = loader.get_skill_content("test-skill")

    loader.reload_skill("test-skill")

    content2 = loader.get_skill_content("test-skill")
    assert content1 == content2

    print("[OK] test_reload_skill")


def test_invalidate_cache():
    """测试清除缓存"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])
    loader.get_skill_content("test-skill")

    assert len(loader._content_cache) == 1

    loader.invalidate_cache()
    assert len(loader._content_cache) == 0

    print("[OK] test_invalidate_cache")


def test_skill_content_dataclass():
    """测试 SkillContent 数据类"""
    import time

    metadata = SkillMetadata(name="test", description="测试", category="general")
    content = SkillContent(
        metadata=metadata,
        instructions="核心指令",
        references={},
        loaded_at=time.time()
    )
    assert content.metadata.name == "test"
    assert content.instructions == "核心指令"
    print("[OK] test_skill_content_dataclass")


def test_get_cache_stats():
    """测试获取缓存统计"""
    tmpdir, skill_dir = _create_temp_skill_dir()

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])

    stats = loader.get_cache_stats()
    assert stats["metadata_count"] >= 1
    assert stats["scan_completed"] is True
    print("[OK] test_get_cache_stats")


def test_scan_nonexistent_dir():
    """测试扫描不存在的目录"""
    loader = SkillLoader()
    loader.scan_skill_dirs(["/nonexistent/directory/path"])
    assert loader._metadata_cache == {}
    print("[OK] test_scan_nonexistent_dir")


def test_skip_hidden_and_examples():
    """测试跳过隐藏目录和 examples"""
    tmpdir = tempfile.mkdtemp()
    skill_tmp = Path(tmpdir)

    for name in [".hidden-skill", "examples"]:
        d = skill_tmp / name
        d.mkdir()
        (d / "SKILL.md").write_text("""---
name: skipped
version: 1.0.0
description: 应该被跳过
category: test
triggers: []
enabled: true
---

# 应被跳过的 Skill
""", encoding="utf-8")

    loader = SkillLoader()
    loader.scan_skill_dirs([str(tmpdir)])
    assert len(loader._metadata_cache) == 0
    print("[OK] test_skip_hidden_and_examples")


def test_load_skill_instructions_convenience():
    """测试便捷加载函数"""
    content = """---
name: test-skill
version: 1.0.0
description: 测试
category: test
tags: [test]
triggers: ["测试"]
enabled: true
---

# 指令正文内容
"""
    tmpdir, skill_dir = _create_temp_skill_dir(content=content)

    instructions = load_skill_instructions(
        skill_dir=str(tmpdir),
        skill_name="test-skill",
        use_cache=False
    )
    assert len(instructions) > 0
    print("[OK] test_load_skill_instructions_convenience")


if __name__ == "__main__":
    print("=" * 50)
    print("运行 Skill 加载器测试")
    print("=" * 50)

    test_scan_skill_dirs()
    test_get_metadata()
    test_get_metadata_not_found()
    test_get_skill_content()
    test_get_skill_content_cached()
    test_get_skill_content_not_found()
    test_list_all_metadata()
    test_reload_skill()
    test_invalidate_cache()
    test_skill_content_dataclass()
    test_get_cache_stats()
    test_scan_nonexistent_dir()
    test_skip_hidden_and_examples()
    test_load_skill_instructions_convenience()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)
