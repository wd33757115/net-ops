# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Detect field-level changes between structured patrol snapshots."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.patrol.command_splitter import canonicalize_command
from src.core.patrol.snapshot_store import PatrolSnapshotStore, SnapshotRecord


@dataclass(frozen=True)
class NetworkChange:
    change_id: str
    run_id: str | None
    device_id: str | None
    command: str | None
    entity_type: str
    entity_key: str
    field: str
    old_value: Any
    new_value: Any
    change_type: str
    previous_snapshot_id: str | None = None
    current_snapshot_id: str | None = None
    detected_at: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["old"] = data.pop("old_value")
        data["new"] = data.pop("new_value")
        return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalize_records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return [{"value": value}]


def _entity_key(row: dict[str, Any], primary_keys: list[str]) -> str:
    keys = primary_keys or ["id", "name", "interface", "port", "peer", "neighbor", "slot"]
    lowered = {str(k).lower(): k for k in row}
    parts: list[str] = []
    for key in keys:
        actual = key if key in row else lowered.get(key.lower())
        if actual is not None:
            parts.append(str(row.get(actual, "")))
    if parts and any(parts):
        return "|".join(parts)
    stable = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return stable[:128]


def detect_changes_between_values(
    previous: Any,
    current: Any,
    *,
    entity_type: str = "record",
    primary_keys: list[str] | None = None,
    run_id: str | None = None,
    device_id: str | None = None,
    command: str | None = None,
    previous_snapshot_id: str | None = None,
    current_snapshot_id: str | None = None,
) -> list[NetworkChange]:
    detected_at = _now()
    prev_rows = _normalize_records(previous)
    curr_rows = _normalize_records(current)
    primary_keys = primary_keys or []
    prev_map = {_entity_key(row, primary_keys): row for row in prev_rows}
    curr_map = {_entity_key(row, primary_keys): row for row in curr_rows}
    changes: list[NetworkChange] = []

    for key in sorted(set(prev_map) - set(curr_map)):
        changes.append(
            NetworkChange(
                change_id=str(uuid.uuid4()),
                run_id=run_id,
                device_id=device_id,
                command=command,
                entity_type=entity_type,
                entity_key=key,
                field="__record__",
                old_value=prev_map[key],
                new_value=None,
                change_type="deleted",
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
                detected_at=detected_at,
            )
        )

    for key in sorted(set(curr_map) - set(prev_map)):
        changes.append(
            NetworkChange(
                change_id=str(uuid.uuid4()),
                run_id=run_id,
                device_id=device_id,
                command=command,
                entity_type=entity_type,
                entity_key=key,
                field="__record__",
                old_value=None,
                new_value=curr_map[key],
                change_type="added",
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
                detected_at=detected_at,
            )
        )

    for key in sorted(set(prev_map) & set(curr_map)):
        prev = prev_map[key]
        curr = curr_map[key]
        for field in sorted(set(prev) | set(curr)):
            if field in {"状态"}:
                continue
            old = prev.get(field)
            new = curr.get(field)
            if _stringify(old).strip() == _stringify(new).strip():
                continue
            changes.append(
                NetworkChange(
                    change_id=str(uuid.uuid4()),
                    run_id=run_id,
                    device_id=device_id,
                    command=command,
                    entity_type=entity_type,
                    entity_key=key,
                    field=str(field),
                    old_value=old,
                    new_value=new,
                    change_type="modified",
                    previous_snapshot_id=previous_snapshot_id,
                    current_snapshot_id=current_snapshot_id,
                    detected_at=detected_at,
                )
            )
    return changes


def detect_changes_between_snapshots(
    previous: SnapshotRecord,
    current: SnapshotRecord,
    *,
    entity_type: str = "record",
    primary_keys: list[str] | None = None,
) -> list[NetworkChange]:
    if previous.structured_json is None or current.structured_json is None:
        if previous.raw_text_hash == current.raw_text_hash:
            return []
        return [
            NetworkChange(
                change_id=str(uuid.uuid4()),
                run_id=current.run_id,
                device_id=current.device_id,
                command=current.command_canonical,
                entity_type="raw_command_output",
                entity_key=current.command_canonical,
                field="raw_text_hash",
                old_value=previous.raw_text_hash,
                new_value=current.raw_text_hash,
                change_type="modified",
                previous_snapshot_id=previous.snapshot_id,
                current_snapshot_id=current.snapshot_id,
                detected_at=_now(),
                confidence=0.5,
            )
        ]
    return detect_changes_between_values(
        previous.structured_json,
        current.structured_json,
        entity_type=entity_type,
        primary_keys=primary_keys,
        run_id=current.run_id,
        device_id=current.device_id,
        command=current.command_canonical,
        previous_snapshot_id=previous.snapshot_id,
        current_snapshot_id=current.snapshot_id,
    )


def ensure_change_table(db_path: str | Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS netops_network_changes (
                change_id TEXT PRIMARY KEY,
                run_id TEXT,
                device_id TEXT,
                command TEXT,
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_type TEXT NOT NULL,
                previous_snapshot_id TEXT,
                current_snapshot_id TEXT,
                detected_at TEXT NOT NULL,
                confidence REAL DEFAULT 1.0
            );
            CREATE INDEX IF NOT EXISTS idx_network_changes_run
                ON netops_network_changes(run_id);
            CREATE INDEX IF NOT EXISTS idx_network_changes_device
                ON netops_network_changes(device_id);
            """
        )


def save_changes(db_path: str | Path, changes: list[NetworkChange]) -> None:
    ensure_change_table(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO netops_network_changes
            (
                change_id, run_id, device_id, command, entity_type, entity_key,
                field, old_value, new_value, change_type,
                previous_snapshot_id, current_snapshot_id, detected_at, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c.change_id,
                    c.run_id,
                    c.device_id,
                    c.command,
                    c.entity_type,
                    c.entity_key,
                    c.field,
                    _stringify(c.old_value),
                    _stringify(c.new_value),
                    c.change_type,
                    c.previous_snapshot_id,
                    c.current_snapshot_id,
                    c.detected_at,
                    c.confidence,
                )
                for c in changes
            ],
        )


def detect_changes_from_params(params: dict[str, Any]) -> dict[str, Any]:
    db_path = params.get("db_path") or params.get("patrol_db")
    entity_type = params.get("entity_type") or "record"
    primary_keys = list(params.get("primary_keys") or [])
    persist = bool(params.get("persist", True))

    if "previous_snapshot" in params or "current_snapshot" in params:
        changes = detect_changes_between_values(
            params.get("previous_snapshot"),
            params.get("current_snapshot"),
            entity_type=entity_type,
            primary_keys=primary_keys,
            device_id=params.get("device_id"),
            command=params.get("command"),
        )
    elif params.get("previous_snapshot_id") and params.get("current_snapshot_id"):
        if not db_path:
            raise ValueError("db_path is required when comparing snapshot IDs")
        store = PatrolSnapshotStore(db_path)
        previous = store.get_snapshot(str(params["previous_snapshot_id"]))
        current = store.get_snapshot(str(params["current_snapshot_id"]))
        if not previous or not current:
            raise ValueError("snapshot not found")
        changes = detect_changes_between_snapshots(
            previous,
            current,
            entity_type=entity_type,
            primary_keys=primary_keys,
        )
    elif params.get("previous_run_id") and params.get("current_run_id"):
        if not db_path:
            raise ValueError("db_path is required when comparing run IDs")
        store = PatrolSnapshotStore(db_path)
        current_snapshots = store.list_run_snapshots(
            str(params["current_run_id"]),
            device_id=params.get("device_id"),
        )
        changes = []
        for current in current_snapshots:
            previous = store.find_snapshot(
                run_id=str(params["previous_run_id"]),
                device_id=current.device_id,
                command_canonical=canonicalize_command(current.command_canonical),
            )
            if previous:
                changes.extend(
                    detect_changes_between_snapshots(
                        previous,
                        current,
                        entity_type=entity_type,
                        primary_keys=primary_keys,
                    )
                )
    elif params.get("current_run_id"):
        if not db_path:
            raise ValueError("db_path is required when comparing current run with history")
        return detect_changes_against_history(
            db_path,
            current_run_id=str(params["current_run_id"]),
            device_id=params.get("device_id"),
            persist=persist,
        )
    else:
        raise ValueError(
            "provide previous_snapshot/current_snapshot, snapshot IDs, "
            "previous_run_id/current_run_id, or current_run_id"
        )

    if db_path and persist:
        save_changes(db_path, changes)
    return {
        "success": True,
        "change_count": len(changes),
        "changes": [c.to_dict() for c in changes],
    }


def detect_changes_against_history(
    db_path: str | Path,
    *,
    current_run_id: str,
    device_id: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Compare every current snapshot with its latest prior snapshot."""
    store = PatrolSnapshotStore(db_path)
    changes: list[NetworkChange] = []
    compared_snapshots = 0
    baseline_snapshots = 0
    for current in store.list_run_snapshots(current_run_id, device_id=device_id):
        previous = store.find_previous_snapshot(
            current_run_id=current_run_id,
            device_id=current.device_id,
            command_canonical=current.command_canonical,
        )
        if not previous:
            baseline_snapshots += 1
            continue
        compared_snapshots += 1
        changes.extend(detect_changes_between_snapshots(previous, current))

    if persist:
        save_changes(db_path, changes)
    return {
        "success": True,
        "current_run_id": current_run_id,
        "compared_snapshots": compared_snapshots,
        "baseline_snapshots": baseline_snapshots,
        "change_count": len(changes),
        "changes": [change.to_dict() for change in changes],
    }
