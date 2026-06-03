"""ExecutionWorkspace 单元测试。"""

import json
from unittest.mock import MagicMock, patch

from src.core.skills.result import ExecutionContext, SkillExecutionResult, SkillStatus
from src.core.skills.workspace import ExecutionWorkspace


@patch("src.core.skills.workspace.get_redis")
def test_workspace_put_and_get(mock_get_redis):
    store: dict[str, str] = {}
    client = MagicMock()

    def hset(key, field, value):
        store[f"{key}:{field}"] = value

    def hget(key, field):
        return store.get(f"{key}:{field}")

    client.hset.side_effect = hset
    client.hget.side_effect = hget
    client.expire.return_value = True
    mock_get_redis.return_value = client

    ser = SkillExecutionResult(
        skill_name="firewall-policy-generator",
        status=SkillStatus.SUCCESS,
        message="ok",
        context=ExecutionContext(source="chat", thread_id="th1", message_id="msg1"),
    )
    assert ExecutionWorkspace.put("th1", "msg1", ser) is True
    legacy = ExecutionWorkspace.get_skill("th1", "msg1", "firewall-policy-generator")
    assert legacy is not None
    assert legacy["skill_name"] == "firewall-policy-generator"
    assert legacy["execution_id"] == ser.execution_id


@patch("src.core.skills.workspace.get_redis")
def test_workspace_no_redis(mock_get_redis):
    mock_get_redis.return_value = None
    ser = SkillExecutionResult(
        skill_name="x",
        status=SkillStatus.SUCCESS,
        context=ExecutionContext(source="chat", thread_id="t", message_id="m"),
    )
    assert ExecutionWorkspace.put("t", "m", ser) is False
