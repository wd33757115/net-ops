# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""生成单条模板验证报告并写入 reports/ 目录。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BEIJING_TZ = timezone(timedelta(hours=8))


@dataclass
class GenerationReport:
    vendor: str
    model: str
    command: str
    category: str
    template_generated: bool
    compile_success: bool
    record_count: int
    field_coverage: int
    validation_score: int
    retry_count: int
    template_path: str | None = None
    skipped_reason: str | None = None
    errors: list[str] | None = None
    parsed_records: list[dict[str, Any]] | None = None
    mode: str = "database"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data.get("errors"):
            data.pop("errors", None)
        if not data.get("skipped_reason"):
            data.pop("skipped_reason", None)
        if not data.get("parsed_records"):
            data.pop("parsed_records", None)
        return data


def save_report(report: GenerationReport, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(BEIJING_TZ).strftime("%Y%m%d_%H%M%S")
    safe_cmd = report.command.replace(" ", "_").replace("/", "_")[:40]
    filename = f"{report.vendor}_{report.model}_{safe_cmd}_{ts}.json"
    path = reports_dir / filename
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_summary(reports: list[GenerationReport], reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(BEIJING_TZ).strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"summary_{ts}.json"
    payload = {
        "generated_at": datetime.now(BEIJING_TZ).isoformat(),
        "total": len(reports),
        "success": sum(1 for r in reports if r.template_generated),
        "reports": [r.to_dict() for r in reports],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
