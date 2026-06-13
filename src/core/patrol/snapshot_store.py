# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""SQLite storage for patrol runs and command snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SnapshotRecord:
    snapshot_id: str
    run_id: str
    device_id: str
    device_name: str
    ip: str | None
    vendor: str | None
    model: str | None
    command: str
    command_canonical: str
    parser_name: str | None
    parser_version: str | None
    observed_at: str
    structured_json: Any
    raw_text: str
    raw_text_hash: str
    parse_status: str


class PatrolSnapshotStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS netops_patrol_runs (
                    run_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    device_count INTEGER DEFAULT 0,
                    command_count INTEGER DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS netops_device_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    ip TEXT,
                    vendor TEXT,
                    model TEXT,
                    command TEXT NOT NULL,
                    command_canonical TEXT NOT NULL,
                    parser_name TEXT,
                    parser_version TEXT,
                    observed_at TEXT NOT NULL,
                    structured_json TEXT,
                    raw_text TEXT,
                    raw_text_hash TEXT NOT NULL,
                    parse_status TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES netops_patrol_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_run_device
                    ON netops_device_snapshots(run_id, device_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_device_command
                    ON netops_device_snapshots(device_id, command_canonical);
                """
            )

    def create_run(
        self,
        *,
        run_id: str | None = None,
        source: str = "imported_file",
        metadata: dict[str, Any] | None = None,
        started_at: str | None = None,
    ) -> str:
        run_id = run_id or str(uuid.uuid4())
        now = started_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO netops_patrol_runs
                (run_id, source, started_at, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, source, now, json.dumps(metadata or {}, ensure_ascii=False)),
            )
        return run_id

    def finish_run(self, run_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT device_id) AS devices, COUNT(*) AS commands
                FROM netops_device_snapshots WHERE run_id=?
                """,
                (run_id,),
            ).fetchone()
            conn.execute(
                """
                UPDATE netops_patrol_runs
                SET completed_at=?, device_count=?, command_count=?
                WHERE run_id=?
                """,
                (now, int(row["devices"] or 0), int(row["commands"] or 0), run_id),
            )

    def save_snapshot(
        self,
        *,
        run_id: str,
        device_id: str,
        device_name: str,
        command: str,
        command_canonical: str,
        raw_text: str,
        ip: str | None = None,
        vendor: str | None = None,
        model: str | None = None,
        observed_at: str | None = None,
        structured_json: Any = None,
        parser_name: str | None = None,
        parser_version: str | None = None,
        parse_status: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        snapshot_id = str(uuid.uuid4())
        raw_hash = hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest()
        status = parse_status or ("parsed" if structured_json is not None else "raw_only")
        created_at = datetime.now(timezone.utc).isoformat()
        observed = observed_at or created_at
        structured_text = (
            json.dumps(structured_json, ensure_ascii=False, default=str)
            if structured_json is not None
            else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO netops_device_snapshots
                (
                    snapshot_id, run_id, device_id, device_name, ip, vendor, model,
                    command, command_canonical, parser_name, parser_version,
                    observed_at, structured_json, raw_text, raw_text_hash,
                    parse_status, start_line, end_line, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    run_id,
                    device_id,
                    device_name,
                    ip,
                    vendor,
                    model,
                    command,
                    command_canonical,
                    parser_name,
                    parser_version,
                    observed,
                    structured_text,
                    raw_text,
                    raw_hash,
                    status,
                    start_line,
                    end_line,
                    created_at,
                ),
            )
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM netops_device_snapshots WHERE snapshot_id=?",
                (snapshot_id,),
            ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def find_snapshot(
        self,
        *,
        run_id: str,
        device_id: str,
        command_canonical: str,
    ) -> SnapshotRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM netops_device_snapshots
                WHERE run_id=? AND device_id=? AND command_canonical=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (run_id, device_id, command_canonical),
            ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def find_previous_snapshot(
        self,
        *,
        current_run_id: str,
        device_id: str,
        command_canonical: str,
    ) -> SnapshotRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM netops_device_snapshots
                WHERE run_id<>? AND device_id=? AND command_canonical=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (current_run_id, device_id, command_canonical),
            ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def list_run_snapshots(self, run_id: str, device_id: str | None = None) -> list[SnapshotRecord]:
        sql = "SELECT * FROM netops_device_snapshots WHERE run_id=?"
        params: list[Any] = [run_id]
        if device_id:
            sql += " AND device_id=?"
            params.append(device_id)
        sql += " ORDER BY device_id, command_canonical"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def _row_to_snapshot(self, row: sqlite3.Row) -> SnapshotRecord:
        structured = json.loads(row["structured_json"]) if row["structured_json"] else None
        return SnapshotRecord(
            snapshot_id=row["snapshot_id"],
            run_id=row["run_id"],
            device_id=row["device_id"],
            device_name=row["device_name"],
            ip=row["ip"],
            vendor=row["vendor"],
            model=row["model"],
            command=row["command"],
            command_canonical=row["command_canonical"],
            parser_name=row["parser_name"],
            parser_version=row["parser_version"],
            observed_at=row["observed_at"],
            structured_json=structured,
            raw_text=row["raw_text"] or "",
            raw_text_hash=row["raw_text_hash"],
            parse_status=row["parse_status"],
        )
