# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""从 SQLite 巡检库发现「有原始输出、无结构化数据」的候选记录。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config_loader import CommandMapping, resolve_device_mapping


@dataclass(frozen=True)
class TemplateCandidate:
    vendor: str
    model: str
    command: str
    sample_output: str
    source_table: str
    device_id: str


def _is_empty_structured(value: str | None) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"null", "none", "[]"}


def _fetch_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    has_run_id: bool,
) -> list[tuple[str, str, str | None, str | None]]:
    """返回 (device_id, command, structured, text_output)。"""
    cur = conn.cursor()
    if has_run_id:
        sql = f"""
            SELECT device_id, command, structured, text_output
            FROM {table}
            WHERE text_output IS NOT NULL AND TRIM(text_output) != ''
            ORDER BY timestamp DESC
        """
    else:
        sql = f"""
            SELECT device_id, command, structured, text_output
            FROM {table}
            WHERE text_output IS NOT NULL AND TRIM(text_output) != ''
            ORDER BY last_update DESC
        """
    try:
        cur.execute(sql)
        return list(cur.fetchall())
    except sqlite3.Error:
        return []


def _load_device_models(devices_db: Path) -> dict[str, str]:
    """device_id (name-ip) → model。"""
    if not devices_db.is_file():
        return {}
    conn = sqlite3.connect(str(devices_db))
    try:
        cur = conn.cursor()
        cur.execute("SELECT device_name, ip, model FROM devices")
        mapping: dict[str, str] = {}
        for name, ip, model in cur.fetchall():
            if not name or not ip:
                continue
            key = f"{name}-{ip}"
            mapping[key] = (model or "").strip()
        return mapping
    finally:
        conn.close()


def discover_missing_template_candidates(
    patrol_db: Path,
    devices_db: Path,
    command_mappings: list[CommandMapping],
    *,
    vendor_filter: str | None = None,
    model_filter: str | None = None,
    command_filter: str | None = None,
) -> list[TemplateCandidate]:
    """
    按 (vendor, model, command) 去重，仅保留 structured 为空的记录。
    不依赖 device-patrol 代码，仅读取其写入的 SQLite 表。
    """
    if not patrol_db.is_file():
        return []

    device_models = _load_device_models(devices_db)
    seen: set[tuple[str, str, str]] = set()
    candidates: list[TemplateCandidate] = []

    with sqlite3.connect(str(patrol_db)) as conn:
        rows: list[tuple[str, str, str | None, str | None, str]] = []
        for table, has_run in (("patrol_data", True), ("baseline_data", False)):
            for device_id, command, structured, text_output in _fetch_rows(
                conn,
                table,
                has_run_id=has_run,
            ):
                if not _is_empty_structured(structured):
                    continue
                rows.append((device_id, command, structured, text_output, table))

        for device_id, command, _structured, text_output, table in rows:
            device_model = device_models.get(device_id, "")
            resolved = resolve_device_mapping(device_model, command_mappings)
            if not resolved:
                continue
            vendor, model = resolved

            if vendor_filter and vendor != vendor_filter:
                continue
            if model_filter and model != model_filter:
                continue
            if command_filter and command.strip() != command_filter.strip():
                continue

            key = (vendor, model, command.strip())
            if key in seen:
                continue
            seen.add(key)

            candidates.append(
                TemplateCandidate(
                    vendor=vendor,
                    model=model,
                    command=command.strip(),
                    sample_output=text_output or "",
                    source_table=table,
                    device_id=device_id,
                )
            )

    return candidates
