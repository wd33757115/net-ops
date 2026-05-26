"""Supervisor v2 图编排单元测试（无 LLM / 无真实设备）。"""

from src.agents.supervisor.graph_v2 import (
    _build_send_payload,
    _merge_params_with_deps,
    _next_runnable_task,
    build_supervisor_graph_v2,
    orchestrator_dispatch,
    route_after_executor_v2,
)
from src.agents.supervisor.models_v2 import ExecutionPlan, SkillTaskSpec


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
