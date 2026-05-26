"""Supervisor v2 图编排单元测试（无 LLM / 无真实设备）。"""

from src.agents.supervisor.graph_v2 import (
    INTERMEDIATE_RESULTS_RESET,
    _build_heuristic_execution_plan,
    _build_send_payload,
    _extract_ticket_id,
    _filter_skill_matches,
    _has_trigger_match,
    _is_knowledge_question,
    _merge_dicts,
    _merge_params_with_deps,
    _next_runnable_task,
    build_supervisor_graph_v2,
    orchestrator_dispatch,
    route_after_executor_v2,
)
from src.skill_system.router import SkillMatch
from src.agents.supervisor.models_v2 import ExecutionPlan, SkillTaskSpec


def test_extract_ticket_id_from_query():
    assert _extract_ticket_id("生成防火墙策略，工单号：rg001") == "rg001"
    assert _extract_ticket_id("ticket_id: ABC-99") == "ABC-99"


def test_knowledge_question_not_rule_scheduled_to_skill():
    assert _is_knowledge_question("交换机接口down了怎么办") is True
    matches = [
        SkillMatch(
            skill_name="device-backup",
            confidence=0.49,
            match_type="semantic",
            reason="语义相似度: 0.49",
        )
    ]
    assert _filter_skill_matches("交换机接口down了怎么办", matches) == []
    plan = _build_heuristic_execution_plan(
        "交换机接口down了怎么办",
        ["device-backup"],
        matches,
        None,
    )
    assert plan is None


def test_heuristic_plan_for_firewall_trigger():
    matches = [
        SkillMatch(
            skill_name="firewall-policy-generator",
            confidence=0.95,
            match_type="trigger",
            reason="匹配触发词: 生成防火墙策略",
        )
    ]
    plan = _build_heuristic_execution_plan(
        "生成防火墙策略，工单号：rg001",
        ["firewall-policy-generator"],
        matches,
        None,
    )
    assert plan is not None
    assert not plan.fallback_to_rag
    assert plan.skills[0].skill_name == "firewall-policy-generator"
    assert plan.skills[0].parameters.get("ticket_id") == "rg001"
    assert _has_trigger_match(matches, ["firewall-policy-generator"])


def test_merge_params_with_deps_injects_previous_output():
    task = SkillTaskSpec(
        skill_name="config-backup",
        parameters={"device": "sw1"},
        depends_on=["device-inspection"],
    )
    intermediate = {
        "device-inspection": {
            "success": True,
            "data": {"devices": ["sw1", "sw2"]},
            "message": "巡检完成",
        }
    }
    params = _merge_params_with_deps(task, intermediate, None, "")
    assert params["device"] == "sw1"
    assert "device-inspection_output" in params
    assert params["previous_data"] == {"devices": ["sw1", "sw2"]}


def test_next_runnable_task_respects_dependencies():
    tasks = [
        SkillTaskSpec(skill_name="a", parameters={}),
        SkillTaskSpec(skill_name="b", parameters={}, depends_on=["a"]),
    ]
    assert _next_runnable_task(tasks, set()).skill_name == "a"
    assert _next_runnable_task(tasks, {"a"}).skill_name == "b"
    assert _next_runnable_task(tasks, {"a", "b"}) is None


def test_merge_dicts_reset_clears_stale_skill_results():
    stale = {"firewall-policy-generator": {"success": False, "error": "old"}}
    assert _merge_dicts(stale, INTERMEDIATE_RESULTS_RESET) == {}
    assert _merge_dicts(stale, {"firewall-policy-generator": {"success": True}})["firewall-policy-generator"]["success"]


def test_orchestrator_runs_after_intermediate_reset():
    """模拟 pre_process 清空后，不应因 checkpoint 残留而跳过 Skill 执行。"""
    plan = ExecutionPlan(
        reasoning="防火墙",
        skills=[SkillTaskSpec(skill_name="firewall-policy-generator", parameters={"ticket_id": "rg001"})],
        execution_mode="parallel",
    )
    state = {
        "execution_plan": plan,
        "intermediate_results": _merge_dicts(
            {"firewall-policy-generator": {"success": False, "error": "stale"}},
            INTERMEDIATE_RESULTS_RESET,
        ),
        "uploaded_file_path": None,
        "ticket_id": "rg001",
        "messages": [],
    }
    result = orchestrator_dispatch(state)
    assert isinstance(result, list)
    assert len(result) == 1
    assert getattr(result[0], "node", None) == "skill_executor_v2"


def test_orchestrator_parallel_fan_out():
    plan = ExecutionPlan(
        reasoning="并行巡检与备份",
        skills=[
            SkillTaskSpec(skill_name="device-inspection", parameters={}),
            SkillTaskSpec(skill_name="config-backup", parameters={}),
        ],
        execution_mode="parallel",
    )
    state = {
        "execution_plan": plan,
        "intermediate_results": {},
        "uploaded_file_path": None,
        "ticket_id": "",
        "messages": [],
    }
    result = orchestrator_dispatch(state)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(getattr(item, "node", None) == "skill_executor_v2" for item in result)


def test_orchestrator_sequential_single_send():
    plan = ExecutionPlan(
        reasoning="先巡检后备份",
        skills=[
            SkillTaskSpec(skill_name="device-inspection", parameters={}),
            SkillTaskSpec(skill_name="config-backup", parameters={}, depends_on=["device-inspection"]),
        ],
        execution_mode="sequential",
    )
    state = {
        "execution_plan": plan,
        "intermediate_results": {},
        "uploaded_file_path": None,
        "ticket_id": "",
        "messages": [],
    }
    result = orchestrator_dispatch(state)
    assert getattr(result, "node", None) == "skill_executor_v2"
    assert result.arg["current_skill_task"].skill_name == "device-inspection"


def test_route_after_executor_loops_on_sequential():
    plan = ExecutionPlan(
        reasoning="顺序执行",
        skills=[
            SkillTaskSpec(skill_name="a", parameters={}),
            SkillTaskSpec(skill_name="b", parameters={}, depends_on=["a"]),
        ],
        execution_mode="sequential",
    )
    state = {"execution_plan": plan, "intermediate_results": {"a": {"success": True}}}
    assert route_after_executor_v2(state) == "orchestrator"


def test_route_after_executor_parallel_goes_to_aggregator():
    plan = ExecutionPlan(
        reasoning="并行",
        skills=[SkillTaskSpec(skill_name="a", parameters={})],
        execution_mode="parallel",
    )
    state = {"execution_plan": plan, "intermediate_results": {"a": {"success": True}}}
    assert route_after_executor_v2(state) == "final_aggregator"


def test_build_supervisor_graph_v2_compiles():
    graph = build_supervisor_graph_v2()
    assert graph is not None
    assert hasattr(graph, "invoke")


def test_build_send_payload_creates_skill_decision():
    plan = ExecutionPlan(reasoning="test", skills=[], execution_mode="parallel")
    state = {
        "execution_plan": plan,
        "intermediate_results": {},
        "uploaded_file_path": "/tmp/x",
        "ticket_id": "T001",
    }
    task = SkillTaskSpec(skill_name="config-backup", parameters={})
    payload = _build_send_payload(state, task)
    assert payload["skill_decision"].skill_name == "config-backup"
    assert payload["skill_decision"].parameters.get("uploaded_file_path") == "/tmp/x"
