# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Build operational network events from low-level changes."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.patrol.change_detector import ensure_change_table


@dataclass(frozen=True)
class NetworkEvent:
    event_id: str
    event_type: str
    severity: str
    device_id: str | None
    entity_type: str
    entity_key: str
    source_change_id: str | None
    run_id: str | None
    occurred_at: str
    status: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _is_down(value: Any) -> bool:
    text = _norm(value)
    return text in {"down", "administratively down", "admin-down", "notconnect", "inactive"}


def _is_up(value: Any) -> bool:
    text = _norm(value)
    return text in {"up", "connected", "active", "established", "normal"}


def _field_in(change: dict[str, Any], names: set[str]) -> bool:
    return _norm(change.get("field")).replace("-", "_") in names


def build_events_from_changes(changes: list[dict[str, Any]]) -> list[NetworkEvent]:
    events: list[NetworkEvent] = []
    occurred_at = _now()
    for change in changes:
        field = _norm(change.get("field")).replace("-", "_")
        old = change.get("old")
        new = change.get("new")
        event_type = None
        severity = None

        if field in {"cpu", "cpu_5s", "cpu_1m", "cpu_5m", "cpu_usage"}:
            value = _to_float(new)
            if value is not None and value >= 90:
                event_type = "CPUHigh"
                severity = "warning"
        elif _field_in(
            change,
            {"status", "protocol", "physical", "physical_status", "oper_status", "line_protocol"},
        ):
            if _is_up(old) and _is_down(new):
                event_type = "InterfaceDown"
                severity = "major"
            elif _is_down(old) and _is_up(new):
                event_type = "InterfaceUp"
                severity = "info"
        elif field in {"state", "bgp_state", "peer_state", "neighbor_state"}:
            if _norm(old) == "established" and _norm(new) != "established":
                event_type = "BGPNeighborLost"
                severity = "critical"
            elif _norm(old) != "established" and _norm(new) == "established":
                event_type = "BGPNeighborEstablished"
                severity = "info"
        elif (
            change.get("entity_type") == "raw_command_output"
            and change.get("field") == "raw_text_hash"
        ):
            command = _norm(change.get("command"))
            if any(
                marker in command
                for marker in ("configuration", "running-config", "current-configuration")
            ):
                event_type = "ConfigChanged"
                severity = "minor"

        if not event_type:
            continue

        events.append(
            NetworkEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                severity=severity or "info",
                device_id=change.get("device_id"),
                entity_type=str(change.get("entity_type") or "unknown"),
                entity_key=str(change.get("entity_key") or ""),
                source_change_id=change.get("change_id"),
                run_id=change.get("run_id"),
                occurred_at=change.get("detected_at") or occurred_at,
                status="open",
                payload={"change": change},
            )
        )
    return events


def ensure_event_table(db_path: str | Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS netops_network_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                device_id TEXT,
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                source_change_id TEXT,
                run_id TEXT,
                occurred_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_network_events_run
                ON netops_network_events(run_id);
            CREATE INDEX IF NOT EXISTS idx_network_events_device
                ON netops_network_events(device_id);
            CREATE INDEX IF NOT EXISTS idx_network_events_type
                ON netops_network_events(event_type);
            """
        )


def save_events(db_path: str | Path, events: list[NetworkEvent]) -> None:
    ensure_event_table(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO netops_network_events
            (
                event_id, event_type, severity, device_id, entity_type, entity_key,
                source_change_id, run_id, occurred_at, status, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e.event_id,
                    e.event_type,
                    e.severity,
                    e.device_id,
                    e.entity_type,
                    e.entity_key,
                    e.source_change_id,
                    e.run_id,
                    e.occurred_at,
                    e.status,
                    json.dumps(e.payload, ensure_ascii=False, default=str),
                )
                for e in events
            ],
        )


def publish_events(events: list[NetworkEvent]) -> list[str]:
    from src.core.events.bus import EventBus
    from src.core.events.domain_event import DomainEvent
    from src.core.events.streams import STREAM_NETWORK_EVENT

    message_ids: list[str] = []
    for event in events:
        msg_id = EventBus.publish(
            STREAM_NETWORK_EVENT,
            DomainEvent(
                event_type=f"network.{event.event_type}",
                source="patrol",
                correlation_id=event.run_id or event.event_id,
                payload=event.to_dict(),
            ),
        )
        if msg_id:
            message_ids.append(msg_id)
    return message_ids


def load_changes_from_db(
    db_path: str | Path,
    *,
    run_id: str | None = None,
    device_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_change_table(db_path)
    sql = "SELECT * FROM netops_network_changes WHERE 1=1"
    params: list[Any] = []
    if run_id:
        sql += " AND run_id=?"
        params.append(run_id)
    if device_id:
        sql += " AND device_id=?"
        params.append(device_id)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    changes = []
    for row in rows:
        item = dict(row)
        item["old"] = item.pop("old_value")
        item["new"] = item.pop("new_value")
        changes.append(item)
    return changes


def build_events_from_params(params: dict[str, Any]) -> dict[str, Any]:
    db_path = params.get("db_path") or params.get("patrol_db")
    changes = params.get("changes")
    if changes is None:
        if not db_path:
            raise ValueError("changes or db_path is required")
        changes = load_changes_from_db(
            db_path,
            run_id=params.get("run_id"),
            device_id=params.get("device_id"),
        )
    events = build_events_from_changes(list(changes or []))
    if db_path and params.get("persist", True):
        save_events(db_path, events)
    message_ids: list[str] = []
    if params.get("publish", False):
        message_ids = publish_events(events)
    return {
        "success": True,
        "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "published_message_ids": message_ids,
    }
