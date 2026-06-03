# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""WorkflowEngine 并行批调度单元测试。"""

from src.core.workflows.engine import WorkflowEngine
from src.core.workflows.registry import WorkflowStepTemplate, WorkflowTemplate
from pathlib import Path


def _fake_template():
    steps = [
        WorkflowStepTemplate(name="step_a", skill_name="skill-a"),
        WorkflowStepTemplate(name="step_b", skill_name="skill-b", parallel_group="pg1"),
        WorkflowStepTemplate(name="step_c", skill_name="skill-c", parallel_group="pg1"),
        WorkflowStepTemplate(name="step_d", skill_name="skill-d"),
    ]
    return WorkflowTemplate(
        name="fake",
        description="",
        version="1",
        steps=steps,
        plugin_dir=Path("."),
    )


class _FakeStep:
    def __init__(self, step_name: str):
        self.step_name = step_name


def test_parallel_batch_indices_detects_group():
    tpl = _fake_template()
    db_steps = [_FakeStep("step_a"), _FakeStep("step_b"), _FakeStep("step_c"), _FakeStep("step_d")]
    batch = WorkflowEngine._parallel_batch_indices(tpl, db_steps, 1)
    assert batch == [1, 2]

    single = WorkflowEngine._parallel_batch_indices(tpl, db_steps, 0)
    assert single == [0]


def test_parallel_batch_indices_single_step_no_group():
    tpl = _fake_template()
    db_steps = [_FakeStep("step_a")]
    assert WorkflowEngine._parallel_batch_indices(tpl, db_steps, 0) == [0]
