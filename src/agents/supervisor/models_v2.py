"""Supervisor v2 协同编排数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionMode = Literal["parallel", "sequential", "conditional"]


class SkillTaskSpec(BaseModel):
    skill_name: str = Field(..., description="Skill 名称")
    parameters: dict[str, Any] = Field(default_factory=dict, description="执行参数")
    depends_on: list[str] = Field(default_factory=list, description="依赖的前置 Skill 名称")


class ExecutionPlanModel(BaseModel):
    """LLM 结构化输出的执行计划。"""

    reasoning: str = Field(..., description="决策理由")
    skills: list[SkillTaskSpec] = Field(default_factory=list, description="待执行 Skill 列表")
    execution_mode: ExecutionMode = Field(default="parallel", description="parallel / sequential / conditional")
    conditions: dict[str, str] = Field(default_factory=dict, description="conditional 模式下的条件描述")
    fallback_to_rag: bool = Field(default=False, description="是否走 RAG 兜底")


@dataclass
class ExecutionPlan:
    reasoning: str
    skills: list[SkillTaskSpec]
    execution_mode: ExecutionMode = "parallel"
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    conditions: dict[str, str] = field(default_factory=dict)
    fallback_to_rag: bool = False

    @classmethod
    def from_model(cls, model: ExecutionPlanModel) -> ExecutionPlan:
        deps = {task.skill_name: list(task.depends_on) for task in model.skills}
        return cls(
            reasoning=model.reasoning,
            skills=model.skills,
            execution_mode=model.execution_mode,
            dependencies=deps,
            conditions=dict(model.conditions),
            fallback_to_rag=model.fallback_to_rag,
        )
