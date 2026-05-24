"""
Skill 管理器

提供 Skill 的后端管理功能：创建、编辑、删除、启用/禁用、热加载等。
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Skill 后端管理器

    提供 Skill 的 CRUD 操作和热加载功能。
    """

    def __init__(self):
        """初始化管理器"""
        self._skills_dir = Path(__file__).parent.parent.parent / "src" / "skills"

    def list_all_skills(self) -> list[dict[str, Any]]:
        """
        获取所有 Skill 列表

        Returns:
            List[Dict]: Skill 信息列表
        """
        try:
            from src.skills.registry import skill_registry

            skills = []
            for skill in skill_registry.list_skills():
                metadata = skill_registry.get_metadata(skill.name)
                skills.append({
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "tags": skill.tags,
                    "enabled": skill.enabled,
                    "version": metadata.version if metadata else "1.0.0",
                    "fallback_to_rag": skill.fallback_to_rag_if_fail
                })

            return skills

        except Exception as e:
            logger.error(f"获取 Skill 列表失败: {e}")
            return []

    def list_file_skills(self) -> list[dict[str, Any]]:
        """
        获取基于 SKILL.md 的 Skill 列表

        Returns:
            List[Dict]: 文件型 Skill 信息列表
        """
        skills = []

        if not self._skills_dir.exists():
            return skills

        for item in self._skills_dir.iterdir():
            if not item.is_dir():
                continue

            if item.name.startswith('.') or item.name == 'examples':
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                # 解析 SKILL.md
                content = skill_md.read_text(encoding='utf-8')
                metadata = self._parse_skill_md_content(content)

                skills.append({
                    "name": metadata.get("name", item.name),
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", "general"),
                    "tags": metadata.get("tags", []),
                    "version": metadata.get("version", "1.0.0"),
                    "skill_path": str(item),
                    "skill_md_path": str(skill_md)
                })

            except Exception as e:
                logger.warning(f"解析 Skill {item.name} 失败: {e}")

        return skills

    def _parse_skill_md_content(self, content: str) -> dict[str, Any]:
        """解析 SKILL.md 内容"""
        import re

        # 匹配 frontmatter
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)

        if match:
            yaml_str = match.group(1)
            try:
                return yaml.safe_load(yaml_str) or {}
            except yaml.YAMLError:
                return {}

        return {}

    def create_skill(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        创建新 Skill

        Args:
            data: 包含 name, description, category, triggers, tags 等

        Returns:
            Dict: {"success": bool, "message": str, "skill_path": str}
        """
        try:
            skill_name = data.get("name", "").strip()

            if not skill_name:
                return {"success": False, "message": "Skill 名称不能为空"}

            # 检查名称格式
            if not self._validate_skill_name(skill_name):
                return {"success": False, "message": "名称只能包含字母、数字和连字符"}

            # 检查是否已存在
            skill_dir = self._skills_dir / skill_name
            if skill_dir.exists():
                return {"success": False, "message": f"Skill '{skill_name}' 已存在"}

            # 创建目录
            skill_dir.mkdir(parents=True, exist_ok=True)

            # 生成 SKILL.md
            skill_md = skill_dir / "SKILL.md"
            content = self._generate_skill_md(data)
            skill_md.write_text(content, encoding='utf-8')

            # 注册到 Registry
            self.reload_skill(skill_name)

            logger.info(f"创建 Skill 成功: {skill_name}")

            return {
                "success": True,
                "message": f"Skill '{skill_name}' 创建成功",
                "skill_path": str(skill_dir)
            }

        except Exception as e:
            logger.error(f"创建 Skill 失败: {e}")
            return {"success": False, "message": f"创建失败: {str(e)}"}

    def update_skill(self, skill_name: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        更新 Skill

        Args:
            skill_name: Skill 名称
            data: 更新数据

        Returns:
            Dict: {"success": bool, "message": str}
        """
        try:
            skill_dir = self._skills_dir / skill_name

            if not skill_dir.exists():
                return {"success": False, "message": f"Skill '{skill_name}' 不存在"}

            skill_md = skill_dir / "SKILL.md"

            # 更新内容
            content = self._generate_skill_md(data)
            skill_md.write_text(content, encoding='utf-8')

            # 重新加载
            self.reload_skill(skill_name)

            logger.info(f"更新 Skill 成功: {skill_name}")

            return {"success": True, "message": f"Skill '{skill_name}' 更新成功"}

        except Exception as e:
            logger.error(f"更新 Skill 失败: {e}")
            return {"success": False, "message": f"更新失败: {str(e)}"}

    def delete_skill(self, skill_name: str) -> dict[str, Any]:
        """
        删除 Skill

        Args:
            skill_name: Skill 名称

        Returns:
            Dict: {"success": bool, "message": str}
        """
        try:
            skill_dir = self._skills_dir / skill_name

            if not skill_dir.exists():
                return {"success": False, "message": f"Skill '{skill_name}' 不存在"}

            # 从 Registry 移除
            self._unregister_skill(skill_name)

            # 删除目录
            import shutil
            shutil.rmtree(skill_dir)

            logger.info(f"删除 Skill 成功: {skill_name}")

            return {"success": True, "message": f"Skill '{skill_name}' 删除成功"}

        except Exception as e:
            logger.error(f"删除 Skill 失败: {e}")
            return {"success": False, "message": f"删除失败: {str(e)}"}

    def toggle_skill(self, skill_name: str, enabled: bool) -> dict[str, Any]:
        """
        启用/禁用 Skill

        Args:
            skill_name: Skill 名称
            enabled: 是否启用

        Returns:
            Dict: {"success": bool, "message": str}
        """
        try:
            from src.skills.registry import skill_registry

            skill = skill_registry.get_skill(skill_name)
            if not skill:
                return {"success": False, "message": f"Skill '{skill_name}' 不存在"}

            skill.enabled = enabled

            status = "启用" if enabled else "禁用"
            logger.info(f"{status} Skill: {skill_name}")

            return {"success": True, "message": f"Skill '{skill_name}' 已{status}"}

        except Exception as e:
            logger.error(f"切换 Skill 状态失败: {e}")
            return {"success": False, "message": f"操作失败: {str(e)}"}

    def reload_skill(self, skill_name: str) -> dict[str, Any]:
        """
        热加载 Skill

        Args:
            skill_name: Skill 名称

        Returns:
            Dict: {"success": bool, "message": str}
        """
        try:
            from src.skill_system import reload_all_skills
            from src.skills.registry import skill_registry

            # 重新扫描文件
            skill_registry.discover_skills_from_files()

            # 重新加载 Skill System
            reload_all_skills()

            logger.info(f"热加载 Skill: {skill_name}")

            return {"success": True, "message": f"Skill '{skill_name}' 已重新加载"}

        except Exception as e:
            logger.error(f"热加载 Skill 失败: {e}")
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def reload_all(self) -> dict[str, Any]:
        """
        重新加载所有 Skill

        Returns:
            Dict: {"success": bool, "message": str, "count": int}
        """
        try:
            from src.skill_system import reload_all_skills
            from src.skills.registry import skill_registry

            # 重新扫描
            count = skill_registry.discover_skills_from_files()

            # 重新加载
            reload_all_skills()

            logger.info(f"重新加载了 {count} 个 Skill")

            return {
                "success": True,
                "message": f"成功重新加载 {count} 个 Skill",
                "count": count
            }

        except Exception as e:
            logger.error(f"重新加载所有 Skill 失败: {e}")
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def get_skill_content(self, skill_name: str) -> str | None:
        """
        获取 Skill 的 SKILL.md 内容

        Args:
            skill_name: Skill 名称

        Returns:
            str: SKILL.md 内容，如果不存在返回 None
        """
        try:
            skill_dir = self._skills_dir / skill_name
            skill_md = skill_dir / "SKILL.md"

            if not skill_md.exists():
                return None

            return skill_md.read_text(encoding='utf-8')

        except Exception as e:
            logger.error(f"读取 Skill 内容失败: {e}")
            return None

    def get_stats(self) -> dict[str, Any]:
        """
        获取 Skill 统计信息

        Returns:
            Dict: 统计数据
        """
        try:
            from src.skills.registry import skill_registry

            skills = skill_registry.list_skills()
            categories = {}

            for skill in skills:
                categories[skill.category] = categories.get(skill.category, 0) + 1

            enabled_count = sum(1 for s in skills if s.enabled)

            return {
                "total_skills": len(skills),
                "enabled_skills": enabled_count,
                "disabled_skills": len(skills) - enabled_count,
                "categories": categories,
                "skills": [
                    {
                        "name": s.name,
                        "category": s.category,
                        "enabled": s.enabled
                    }
                    for s in skills
                ]
            }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def _validate_skill_name(self, name: str) -> bool:
        """验证 Skill 名称格式"""
        import re
        return bool(re.match(r'^[a-zA-Z0-9\-_]+$', name))

    def _unregister_skill(self, skill_name: str):
        """从 Registry 移除 Skill"""
        try:
            from src.skills.registry import skill_registry

            # 从 _skills 字典中移除
            if skill_name in skill_registry._skills:
                del skill_registry._skills[skill_name]

            if skill_name in skill_registry._metadata_cache:
                del skill_registry._metadata_cache[skill_name]

        except Exception as e:
            logger.warning(f"从 Registry 移除 Skill 失败: {e}")

    def _generate_skill_md(self, data: dict[str, Any]) -> str:
        """生成标准化 SKILL.md 文件内容 (v2.0)"""
        try:
            from src.skill_system.metadata import create_skill_md

            skill_name = data.get("name", "")
            description = data.get("description", "")
            category = data.get("category", "general")
            tags = data.get("tags", [])
            version = data.get("version", "1.0.0")
            author = data.get("author", "NetOps Team")
            triggers = data.get("triggers", [])
            inputs = data.get("inputs", [])
            outputs = data.get("outputs", [])

            if not inputs:
                inputs = [{"name": "param1", "type": "string", "required": False, "description": "输入参数"}]
            if not outputs:
                outputs = [{"name": "result", "type": "text", "description": "执行结果"}]
            if not triggers:
                triggers = [f"使用{skill_name}"]

            return create_skill_md(
                skill_name=skill_name,
                description=description,
                category=category,
                tags=tags,
                author=author,
                triggers=triggers,
                version=version,
                inputs=inputs,
                outputs=outputs,
            )

        except ImportError as e:
            logger.warning(f"无法导入 metadata 模板，使用基础格式: {e}")
            frontmatter = {
                "name": data.get("name", ""),
                "version": data.get("version", "1.0.0"),
                "description": data.get("description", ""),
                "category": data.get("category", "general"),
                "tags": data.get("tags", []),
                "author": data.get("author", "NetOps Team"),
                "triggers": data.get("triggers", []),
                "inputs": data.get("inputs", []),
                "outputs": data.get("outputs", []),
                "enabled": data.get("enabled", True),
                "fallback_to_rag": data.get("fallback_to_rag", True),
            }
            yaml_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
            instructions = data.get("instructions", f"# {data.get('name', '')}\n\n{data.get('description', '')}")
            return f"---\n{yaml_str}---\n\n{instructions}\n"


# 全局单例
_skill_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """获取 Skill 管理器单例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
