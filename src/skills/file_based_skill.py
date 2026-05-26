"""
基于 SKILL.md 的 Skill 实现（注册到 skill_registry 供 Supervisor 执行）。
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, PrivateAttr

from src.skill_system.metadata import SkillMetadata
from src.skills.skill_base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


def _dummy_handler(*args, **kwargs):
    """占位 handler；实际逻辑在 execute 中。"""
    pass


def create_params_model(metadata: SkillMetadata) -> type[BaseModel]:
    """根据 SKILL.md inputs 动态生成 Pydantic 参数模型。"""
    annotations: dict[str, Any] = {}
    field_definitions: dict[str, Any] = {}

    for inp in metadata.inputs:
        if inp.type == "string":
            field_type = Optional[str]
        elif inp.type in ("integer", "int"):
            field_type = Optional[int]
        elif inp.type in ("number", "float"):
            field_type = Optional[float]
        elif inp.type in ("boolean", "bool"):
            field_type = Optional[bool]
        elif inp.type in ("array", "list"):
            field_type = Optional[list[Any]]
        elif inp.type in ("object", "dict"):
            field_type = Optional[dict[str, Any]]
        else:
            field_type = Optional[Any]

        annotations[inp.name] = field_type
        default_value = inp.default if inp.default is not None else None
        field_definitions[inp.name] = Field(default=default_value, description=inp.description)

    if not field_definitions:
        return BaseModel

    attrs = dict(field_definitions)
    attrs["__annotations__"] = annotations
    return type("SkillParams", (BaseModel,), attrs)


class FileBasedSkill(BaseSkill):
    """SKILL.md 驱动的 Skill；元数据通过 PrivateAttr 保存（兼容 Pydantic v2）。"""

    _metadata: SkillMetadata = PrivateAttr()

    def __init__(self, skill_metadata: SkillMetadata):
        super().__init__(
            name=skill_metadata.name,
            description=skill_metadata.description,
            parameters=create_params_model(skill_metadata),
            handler=_dummy_handler,
            category=skill_metadata.category,
            tags=list(skill_metadata.tags or []),
            fallback_to_rag_if_fail=skill_metadata.fallback_to_rag,
            enabled=skill_metadata.enabled,
        )
        object.__setattr__(self, "_metadata", skill_metadata)

    def get_skill_metadata(self) -> SkillMetadata | None:
        from src.skills.registry import skill_registry

        meta = getattr(self, "_metadata", None)
        if meta is not None:
            return meta
        return skill_registry.get_metadata(self.name)

    def refresh_metadata(self, skill_metadata: SkillMetadata) -> None:
        object.__setattr__(self, "_metadata", skill_metadata)

    async def execute(self, **kwargs) -> SkillResult:
        from src.skills.registry import skill_registry

        try:
            metadata = self.get_skill_metadata()
            task_name = skill_registry._resolve_celery_task(self.name, metadata)

            if task_name:
                return await self._execute_with_celery(task_name, kwargs)

            from src.skill_system import get_skill_system

            instructions = get_skill_system().get_skill_instructions(self.name)
            return await self._execute_with_llm(instructions, kwargs)
        except Exception as e:
            logger.exception("Skill %s 执行失败", self.name)
            return SkillResult(
                success=False,
                message=f"Skill 执行失败: {str(e)}",
                error=str(e),
            )

    async def _execute_with_celery(self, task_name: str, params: dict) -> SkillResult:
        from src.core.celery_tasks import tasks
        from src.skills.registry import skill_registry

        task_func = getattr(tasks, task_name, None)
        if not task_func:
            return SkillResult(
                success=False,
                message=f"找不到任务函数: {task_name}",
                error=f"Task {task_name} not found",
            )

        params = dict(params)
        params = skill_registry._prepare_task_params(task_name, params)

        if task_name == "execute_firewall_policy_task":
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            test_file = os.path.join(base_dir, "tools", "firewall-policy", "test_policy.xlsx")
            if not params.get("policy_file_url") and os.path.exists(test_file):
                params["policy_file_url"] = test_file
            if not params.get("ticket_id"):
                params["ticket_id"] = f"POLICY_{params.get('thread_id', '000')}"
            if not params.get("ticket_title"):
                params["ticket_title"] = "防火墙策略生成"

        from src.core.celery_tasks.celery_exec import (
            CeleryWorkerUnavailableError,
            wait_celery_task_result,
        )

        result = task_func.delay(**params)
        try:
            task_result = wait_celery_task_result(result)
        except CeleryWorkerUnavailableError as exc:
            return SkillResult(success=False, message=str(exc), error="no_celery_worker")
        except TimeoutError as exc:
            return SkillResult(success=False, message=str(exc), error="celery_timeout")

        if isinstance(task_result, dict):
            return SkillResult(**task_result)
        return SkillResult(success=True, message=str(task_result), data={"raw_result": task_result})

    async def _execute_with_llm(self, instructions: str, params: dict) -> SkillResult:
        from langchain_deepseek import ChatDeepSeek

        from src.common.config import get_settings

        settings = get_settings()
        llm = ChatDeepSeek(
            model=settings.LLM_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=0.3,
            request_timeout=60,
        )

        prompt = f"""{instructions}

用户参数：
{json.dumps(params, ensure_ascii=False, indent=2)}

请根据以上指令和参数，执行 Skill 并返回结果。

返回格式：
{{
  "success": true/false,
  "message": "结果描述",
  "data": {{...}}
}}
"""

        try:
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return SkillResult(**result)
            return SkillResult(
                success=True,
                message="Skill 执行完成",
                data={"raw_output": content},
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"LLM 执行失败: {str(e)}",
                error=str(e),
            )
