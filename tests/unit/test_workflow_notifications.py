"""Workflow 通知策略配置测试。"""

from src.core.workflows.registry import WorkflowCompletionConfig, _parse_workflow_file
from pathlib import Path


def test_parse_notify_each_step_from_yaml(tmp_path):
    wf = tmp_path / "WORKFLOW.yaml"
    wf.write_text(
        """
name: test-wf
description: test
version: "1.0"
steps:
  - name: s1
    skill: my-skill
    inputs:
      ticket_id: ${context.ticket_id}
on_complete:
  message: done
  notify_each_step: true
  notify_on_failure: false
  notification:
    title: ok
    level: success
""",
        encoding="utf-8",
    )
    tpl = _parse_workflow_file(wf)
    assert tpl is not None
    assert tpl.on_complete.notify_each_step is True
    assert tpl.on_complete.notify_on_failure is False


def test_default_notify_flags():
    oc = WorkflowCompletionConfig()
    assert oc.notify_each_step is False
    assert oc.notify_on_failure is True
