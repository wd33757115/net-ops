# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""EventBus 与 Consumer 单元测试。"""

from unittest.mock import patch

from src.core.events.bus import EventBus
from src.core.events.domain_event import DomainEvent
from src.core.events.publishers import publish_skill_execution_event
from src.core.events.streams import STREAM_SKILL_EXECUTION
from src.core.skills.result import ExecutionContext, SkillExecutionResult, SkillStatus


class FakeRedis:
    def __init__(self):
        self.streams: dict[str, list[tuple[str, dict]]] = {}
        self.groups: set[tuple[str, str]] = set()
        self.kv: dict[str, str] = {}
        self._id_counter = 0

    def xadd(self, stream, fields, maxlen=None, approximate=True):
        self._id_counter += 1
        msg_id = f"{self._id_counter}-0"
        self.streams.setdefault(stream, []).append((msg_id, fields))
        if len(self.streams[stream]) > (maxlen or 100000):
            self.streams[stream] = self.streams[stream][-(maxlen or 100000) :]
        return msg_id

    def xgroup_create(self, stream, group, id="0", mkstream=True):
        if mkstream:
            self.streams.setdefault(stream, [])
        key = (stream, group)
        if key in self.groups:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups.add(key)

    def xreadgroup(self, groupname, consumername, streams, count=1, block=0):
        out = []
        for stream, marker in streams.items():
            if marker != ">":
                continue
            pending = [(mid, fld) for mid, fld in self.streams.get(stream, []) if True]
            if not pending:
                continue
            # 简化：每次返回最早未 ack 的一条（测试用）
            ack_key = f"ack:{stream}:{groupname}"
            idx = int(self.kv.get(ack_key, "0"))
            items = self.streams.get(stream, [])
            if idx >= len(items):
                continue
            mid, fld = items[idx]
            self.kv[ack_key] = str(idx + 1)
            out.append((stream, [(mid, fld)]))
        return out or None

    def xack(self, stream, group, msg_id):
        return 1

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def exists(self, key):
        return 1 if key in self.kv else 0

    def xrevrange(self, stream, count=50):
        items = self.streams.get(stream, [])
        return list(reversed(items[-count:]))

    def xinfo_groups(self, stream):
        return [{"name": g[1], "pending": 0, "consumers": 1, "last-delivered-id": "0-0"} for g in self.groups if g[0] == stream]


@patch("src.core.events.bus.get_redis")
@patch("src.common.config.get_settings")
def test_event_bus_publish(mock_settings, mock_get_redis):
    fake = FakeRedis()
    mock_get_redis.return_value = fake
    mock_settings.return_value.EVENT_BUS_ENABLED = True
    mock_settings.return_value.EVENT_BUS_STREAM_MAXLEN = 1000

    event = DomainEvent(event_type="skill.executed", correlation_id="msg-1", payload={"skill_name": "x"})
    msg_id = EventBus.publish(STREAM_SKILL_EXECUTION, event)
    assert msg_id is not None
    assert len(fake.streams[STREAM_SKILL_EXECUTION]) == 1


@patch("src.core.events.bus.get_redis")
@patch("src.common.config.get_settings")
def test_publish_skill_execution_event(mock_settings, mock_get_redis):
    fake = FakeRedis()
    mock_get_redis.return_value = fake
    mock_settings.return_value.EVENT_BUS_ENABLED = True
    mock_settings.return_value.EVENT_BUS_STREAM_MAXLEN = 1000

    ser = SkillExecutionResult(
        skill_name="firewall-policy-generator",
        status=SkillStatus.SUCCESS,
        message="ok",
        context=ExecutionContext(source="chat", user_id="u1", message_id="m1"),
    )
    publish_skill_execution_event(ser)
    assert STREAM_SKILL_EXECUTION in fake.streams


@patch("src.core.events.consumers.audit.write_audit_log")
def test_audit_consumer_handles_skill_event(mock_audit):
    from src.core.events.consumers.audit import AuditConsumer

    event = DomainEvent(
        event_type="skill.executed",
        correlation_id="m1",
        source="chat",
        payload={"skill_name": "test-skill", "execution_id": "e1", "status": "success", "user_id": "u1"},
    )
    AuditConsumer().handle(event)
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "skill_execute"
