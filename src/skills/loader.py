# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

from .registry import skill_registry

logger = logging.getLogger(__name__)


class LegacyPythonSkillLoader:
    """
    遗留 Python Skill 加载器（仅用于非 examples 目录下的 *_skill.py）。

    生产环境 Skill 应使用 SKILL.md + bootstrap_skills()。
    """

    def __init__(self, skills_dir: str = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path(__file__).parent

        logger.info("Legacy Python Skill 扫描目录: %s", self.skills_dir)

    def scan_and_load(self) -> int:
        loaded_count = 0
        try:
            skill_files = list(self.skills_dir.rglob("*_skill.py"))
            for skill_file in skill_files:
                if "__pycache__" in str(skill_file) or "test_" in str(skill_file):
                    continue
                if f"{os.sep}examples{os.sep}" in str(skill_file):
                    continue

                module_path = self._file_to_module(skill_file)
                try:
                    module = importlib.import_module(module_path)
                    if hasattr(module, "register_skill"):
                        register_func = getattr(module, "register_skill")
                        if callable(register_func):
                            register_func()
                            loaded_count += 1
                            logger.info("加载遗留 Python Skill 模块: %s", module_path)
                except Exception as e:
                    logger.error("加载模块 %s 失败: %s", module_path, e)
        except Exception as e:
            logger.error("扫描技能目录失败: %s", e)
        return loaded_count

    def _file_to_module(self, file_path: Path) -> str:
        relative_path = file_path.relative_to(self.skills_dir.parent.parent)
        return str(relative_path).replace(".py", "").replace(os.sep, ".")


def load_all_skills(rag_service=None, skill_dirs: list[str] | None = None) -> int:
    """
    统一 Skill 加载入口（SKILL.md + SkillSystem）。

    不再默认扫描 examples/ 下的遗留 Python Skill。
    """
    from src.skills.bootstrap import bootstrap_skills

    return bootstrap_skills(
        rag_service=rag_service,
        skill_dirs=skill_dirs,
        force=False,
    )


# 向后兼容别名
SkillLoader = LegacyPythonSkillLoader


def get_available_skill_files() -> list:
    skills_dir = Path(__file__).parent
    files = []
    for skill_file in skills_dir.rglob("*_skill.py"):
        if "__pycache__" not in str(skill_file) and f"{os.sep}examples{os.sep}" not in str(skill_file):
            files.append(str(skill_file))
    return sorted(files)


if __name__ == "__main__":
    from src.skills.bootstrap import bootstrap_skills

    print(f"bootstrap 完成: {bootstrap_skills(force=True)} 个 Skill")
