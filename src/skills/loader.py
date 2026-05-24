from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

from .registry import skill_registry

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    技能加载器 - 自动扫描并注册所有技能
    
    扫描规则：
    1. 扫描 src/skills/ 目录下所有以 '_skill.py' 结尾的文件
    2. 查找文件中名为 'register_skill' 的函数并执行
    3. 支持嵌套目录扫描（如 src/skills/examples/）
    """

    def __init__(self, skills_dir: str = None):
        """
        初始化加载器
        
        Args:
            skills_dir: 技能目录路径，默认为 src/skills/
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path(__file__).parent

        logger.info(f"技能加载器初始化，扫描目录: {self.skills_dir}")

    def scan_and_load(self) -> int:
        """
        扫描并加载所有技能
        
        Returns:
            int: 成功加载的技能数量
        """
        loaded_count = 0

        try:
            # 递归扫描所有 _skill.py 文件
            skill_files = list(self.skills_dir.rglob("*_skill.py"))
            logger.info(f"发现 {len(skill_files)} 个技能文件")

            for skill_file in skill_files:
                # 跳过 __pycache__ 和测试文件
                if "__pycache__" in str(skill_file) or "test_" in str(skill_file):
                    continue

                # 计算模块路径
                module_path = self._file_to_module(skill_file)

                try:
                    # 导入模块
                    module = importlib.import_module(module_path)

                    # 查找 register_skill 函数
                    if hasattr(module, "register_skill"):
                        register_func = getattr(module, "register_skill")
                        if callable(register_func):
                            register_func()
                            loaded_count += 1
                            logger.info(f"成功加载技能模块: {module_path}")
                    else:
                        logger.warning(f"模块 {module_path} 未定义 register_skill 函数")

                except Exception as e:
                    logger.error(f"加载模块 {module_path} 失败: {e}")

        except Exception as e:
            logger.error(f"扫描技能目录失败: {e}")

        return loaded_count

    def _file_to_module(self, file_path: Path) -> str:
        """
        将文件路径转换为模块路径
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 模块路径（如 src.skills.examples.firewall_policy_skill）
        """
        # 计算相对路径
        relative_path = file_path.relative_to(self.skills_dir.parent.parent)

        # 移除 .py 后缀并替换路径分隔符
        module_path = str(relative_path).replace(".py", "").replace(os.sep, ".")

        return module_path

    def list_available_skills(self) -> list:
        """
        列出所有可加载的技能文件
        
        Returns:
            list: 技能文件路径列表
        """
        skill_files = []

        try:
            files = list(self.skills_dir.rglob("*_skill.py"))
            for skill_file in files:
                if "__pycache__" not in str(skill_file):
                    skill_files.append(str(skill_file))
        except Exception as e:
            logger.error(f"列出技能文件失败: {e}")

        return sorted(skill_files)


def load_all_skills() -> int:
    """
    便捷函数：加载所有技能
    
    Returns:
        int: 成功加载的技能数量
    """
    discovered = 0
    try:
        discovered = skill_registry.discover_skills_from_files()
    except Exception as e:
        logger.warning(f"文件驱动 Skill 加载失败: {e}")

    loader = SkillLoader()
    count = loader.scan_and_load()
    logger.info(f"技能加载完成，共加载 {count} 个 Python Skill，发现 {discovered} 个文件驱动 Skill")
    return count + discovered


def get_available_skill_files() -> list:
    """
    获取所有可加载的技能文件列表
    
    Returns:
        list: 技能文件路径列表
    """
    loader = SkillLoader()
    return loader.list_available_skills()


# 自动加载（当模块被导入时）
try:
    load_all_skills()
except Exception as e:
    logger.warning(f"自动加载技能失败（可能是首次导入）: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("技能加载器测试")
    print("=" * 60)

    print("\n[1] 列出可用技能文件...")
    files = get_available_skill_files()
    for i, f in enumerate(files, 1):
        print(f"    {i}. {f}")

    print("\n[2] 加载所有技能...")
    count = load_all_skills()
    print(f"    成功加载 {count} 个技能")

    print("\n[3] 当前注册的技能...")
    stats = skill_registry.get_statistics()
    print(f"    技能总数: {stats['total_skills']}")
    if stats["categories"]:
        print("    分类统计:")
        for cat, cnt in stats["categories"].items():
            print(f"      - {cat}: {cnt} 个")

    print("\n" + "=" * 60)
    print("加载完成!")
    print("=" * 60)
