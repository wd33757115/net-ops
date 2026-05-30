"""Workflow 表达式与注册表单元测试。"""

from src.core.workflows.expression import build_step_env, resolve_inputs, resolve_value
from src.core.workflows.registry import get_template, load_workflows


def test_load_firewall_workflow_plugin():
    load_workflows(force=True)
    tpl = get_template("itsm-firewall-change")
    assert tpl is not None
    assert len(tpl.steps) == 3
    assert tpl.steps[0].skill_name == "firewall-policy-generator"
    assert tpl.steps[2].when == "${context.callback_url}"


def test_resolve_active_steps_without_callback():
    from src.core.workflows.registry import format_steps_flow, resolve_active_steps

    load_workflows(force=True)
    tpl = get_template("itsm-firewall-change")
    ctx = {"ticket_id": "REQ2025", "policy_file_url": "/tmp/p.xlsx"}
    active = resolve_active_steps(tpl, ctx)
    assert len(active) == 2
    assert active[-1].name == "change_ticket"
    assert format_steps_flow(active) == "生成配置 ZIP → 编写变更工单 Excel"


def test_resolve_active_steps_with_callback():
    from src.core.workflows.registry import resolve_active_steps

    load_workflows(force=True)
    tpl = get_template("itsm-firewall-change")
    ctx = {"ticket_id": "REQ2025", "callback_url": "http://cb"}
    active = resolve_active_steps(tpl, ctx)
    assert len(active) == 3
    assert active[-1].name == "itsm_callback"


def test_resolve_context_expression():
    env = {"context": {"ticket_id": "T001"}, "run": {"id": "run-1"}}
    assert resolve_value("${context.ticket_id}", env) == "T001"
    assert resolve_value("${run.id}", env) == "run-1"


def test_resolve_brace_style_notification():
    env = {"context": {"ticket_id": "REQ2025"}, "run": {"id": "run-1"}}
    assert resolve_value("变更工单已完成 ({context.ticket_id})", env) == "变更工单已完成 (REQ2025)"


def test_resolve_step_artifacts_expression():
    env = build_step_env(
        context={"ticket_id": "T1"},
        run_id="run-1",
        ticket_id="T1",
        step_records=[],
        current_step_index=0,
    )
    env["steps"] = {
        "policy_generation": {
            "result": {"manifest": {"devices": []}},
            "artifacts": {"config_zip": {"file_key": "fk1", "download_url": "http://x"}},
        }
    }
    params = resolve_inputs(
        {
            "manifest": "${steps.policy_generation.result.manifest}",
            "config_file_key": "${steps.policy_generation.artifacts.config_zip.file_key}",
        },
        env,
    )
    assert params["manifest"] == {"devices": []}
    assert params["config_file_key"] == "fk1"
