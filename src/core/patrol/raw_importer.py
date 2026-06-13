# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Import offline raw patrol captures into the snapshot store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.patrol.command_splitter import (
    infer_device_from_filename,
    inspect_raw_capture,
    split_cli_capture,
)
from src.core.patrol.snapshot_store import PatrolSnapshotStore


def _read_text_best_effort(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def import_raw_capture(
    *,
    file_path: str | Path,
    db_path: str | Path,
    run_id: str | None = None,
    device_name: str | None = None,
    ip: str | None = None,
    vendor: str | None = None,
    model: str | None = None,
    observed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(file_path)
    text = _read_text_best_effort(path)
    inferred_name, inferred_ip = infer_device_from_filename(path)
    inspected = inspect_raw_capture(text)
    device_name = device_name or inspected.device_name or inferred_name or path.stem
    ip = ip or inferred_ip
    device_id = f"{device_name}-{ip}" if ip else device_name
    blocks = split_cli_capture(text, device_name=device_name)

    store = PatrolSnapshotStore(db_path)
    rid = store.create_run(
        run_id=run_id,
        source="imported_file",
        metadata={
            "file_path": str(path),
            "prompt_style": inspected.prompt_style,
            **(metadata or {}),
        },
        started_at=observed_at,
    )

    snapshot_ids: list[str] = []
    for block in blocks:
        snapshot_ids.append(
            store.save_snapshot(
                run_id=rid,
                device_id=device_id,
                device_name=device_name,
                ip=ip,
                vendor=vendor,
                model=model,
                command=block.command,
                command_canonical=block.command_canonical,
                raw_text=block.raw_output,
                observed_at=observed_at or inspected.observed_at_text,
                parse_status="raw_only",
                start_line=block.start_line,
                end_line=block.end_line,
            )
        )
    store.finish_run(rid)
    return {
        "success": True,
        "run_id": rid,
        "device_id": device_id,
        "device_name": device_name,
        "ip": ip,
        "command_count": len(blocks),
        "snapshot_ids": snapshot_ids,
        "commands": [b.command_canonical for b in blocks],
    }


def import_raw_path(
    *,
    file_path: str | Path,
    db_path: str | Path,
    run_id: str | None = None,
    vendor: str | None = None,
    model: str | None = None,
    observed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Import one capture file or every txt/log capture in a directory."""
    path = Path(file_path)
    if path.is_file():
        return import_raw_capture(
            file_path=path,
            db_path=db_path,
            run_id=run_id,
            vendor=vendor,
            model=model,
            observed_at=observed_at,
            metadata=metadata,
        )
    if not path.is_dir():
        raise FileNotFoundError(f"巡检数据路径不存在: {path}")

    files = sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in {".txt", ".log"}
    )
    if not files:
        raise ValueError(f"目录中未发现 txt/log 巡检文件: {path}")

    rid = run_id
    imported: list[dict[str, Any]] = []
    for candidate in files:
        result = import_raw_capture(
            file_path=candidate,
            db_path=db_path,
            run_id=rid,
            vendor=vendor,
            model=model,
            observed_at=observed_at,
            metadata={
                "source_directory": str(path),
                **(metadata or {}),
            },
        )
        rid = result["run_id"]
        imported.append(result)

    return {
        "success": True,
        "run_id": rid,
        "db_path": str(db_path),
        "source_path": str(path),
        "file_count": len(imported),
        "device_count": len({item["device_id"] for item in imported}),
        "command_count": sum(item["command_count"] for item in imported),
        "snapshot_ids": [
            snapshot_id
            for item in imported
            for snapshot_id in item["snapshot_ids"]
        ],
        "files": [
            {
                "file_path": str(candidate),
                "device_id": result["device_id"],
                "command_count": result["command_count"],
            }
            for candidate, result in zip(files, imported, strict=True)
        ],
    }
