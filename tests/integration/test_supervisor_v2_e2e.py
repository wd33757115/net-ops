# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Supervisor v2 端到端集成测试（Mock LLM，不依赖真实设备）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agents.supervisor.graph_v2 import build_supervisor_graph_v2
from src.agents.supervisor.models_v2 import ExecutionPlanModel, SkillTaskSpec
from src.skills.skill_base import SkillResult


def _mock_plan(**kwargs) -> ExecutionPlanModel:
    defaults = {
        "reasoning": "测试计划",
        "skills": [],
        "execution_mode": "parallel",
        "conditions": {},
        "fallback_to_rag": False,
    }
    defaults.update(kwargs)
    return ExecutionPlanModel(**defaults)


@pytest.fixture
def graph_v2():
    return build_supervisor_graph_v2()


@pytest.fixture
def mock_skill_execute():
    async def _execute(decision, async_mode=False):
        return SkillResult(
            success=True,
            message=f"{decision.skill_name} 执行成功（mock）",
            data={"skill": decision.skill_name, "mock": True},
            execution_time_ms=10,
        )

    with patch(
        "src.agents.supervisor.graph_v2._execute_skill_decision",
        new=AsyncMock(side_effect=_execute),
    ):
        yield


def test_e2e_single_skill_parallel(graph_v2, mock_skill_execute):
    plan = _mock_plan(
        reasoning="单 Skill 巡检",
        skills=[SkillTaskSpec(skill_name="device-patrol", parameters={"device_name": "sw1"})],
        execution_mode="parallel",
    )
    with patch("src.agents.supervisor.graph_v2.llm_with_execution_plan") as mock_llm:
        mock_llm.invoke = MagicMock(return_value=plan)
        state = graph_v2.invoke(
            {
                "messages": [HumanMessage(content="对 sw1 做设备巡检")],
                "source": "chat",
            },
            config={"configurable": {"thread_id": "e2e-single"}},
        )

    assert state.get("intermediate_results")
    assert "device-patrol" in state["intermediate_results"]
    assert state["intermediate_results"]["device-patrol"]["success"] is True
    last_msg = state["messages"][-1].content
    assert "device-patrol" in last_msg or "协同执行完成" in last_msg


def test_e2e_multi_skill_parallel(graph_v2, mock_skill_execute):
    plan = _mock_plan(
        reasoning="并行巡检与备份",
        skills=[
            SkillTaskSpec(skill_name="device-patrol", parameters={}),
            SkillTaskSpec(skill_name="device-backup", parameters={}),
        ],
        execution_mode="parallel",
    )
    with patch("src.agents.supervisor.graph_v2.llm_with_execution_plan") as mock_llm:
        mock_llm.invoke = MagicMock(return_value=plan)
        state = graph_v2.invoke(
            {
                "messages": [HumanMessage(content="同时巡检设备并备份配置")],
                "source": "chat",
            },
            config={"configurable": {"thread_id": "e2e-parallel"}},
        )

    results = state.get("intermediate_results") or {}
    assert "device-patrol" in results
    assert "device-backup" in results
    assert all(r.get("success") for r in results.values())


def test_e2e_sequential_collaboration(graph_v2, mock_skill_execute):
    call_order: list[str] = []

    async def _sequential_execute(decision, async_mode=False):
        call_order.append(decision.skill_name)
        return SkillResult(
            success=True,
            message=f"{decision.skill_name} done",
            data={"step": decision.skill_name},
            execution_time_ms=5,
        )

    plan = _mock_plan(
        reasoning="先巡检后备份",
        skills=[
            SkillTaskSpec(skill_name="device-patrol", parameters={}),
            SkillTaskSpec(
                skill_name="device-backup",
                parameters={},
                depends_on=["device-patrol"],
            ),
        ],
        execution_mode="sequential",
    )

    with patch(
        "src.agents.supervisor.graph_v2._execute_skill_decision",
        new=AsyncMock(side_effect=_sequential_execute),
    ), patch("src.agents.supervisor.graph_v2.llm_with_execution_plan") as mock_llm:
        mock_llm.invoke = MagicMock(return_value=plan)
        state = graph_v2.invoke(
            {
                "messages": [HumanMessage(content="先巡检设备，再根据结果备份配置")],
                "source": "chat",
            },
            config={"configurable": {"thread_id": "e2e-sequential"}},
        )

    assert call_order == ["device-patrol", "device-backup"]
    backup_params_skill = state.get("intermediate_results", {}).get("device-backup")
    assert backup_params_skill is not None
    assert backup_params_skill["success"] is True


def test_e2e_rag_fallback(graph_v2):
    plan = _mock_plan(reasoning="知识问答", skills=[], fallback_to_rag=True)
    with patch("src.agents.supervisor.graph_v2.llm_with_execution_plan") as mock_llm, patch(
        "src.agents.supervisor.graph_v2.knowledge_qa_node",
        return_value={"messages": [HumanMessage(content="RAG mock answer")]},
    ) as mock_rag:
        mock_llm.invoke = MagicMock(return_value=plan)
        state = graph_v2.invoke(
            {
                "messages": [HumanMessage(content="什么是防火墙")],
                "source": "chat",
            },
            config={"configurable": {"thread_id": "e2e-rag"}},
        )
        mock_rag.assert_called_once()
        assert state.get("next_agent") == "end"
