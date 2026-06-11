#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""TextFSM Generator Skill CLI 入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_templates import generate_templates  # noqa: E402


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="TextFSM Generator — 从巡检原始输出生成 Parser 模板")
    parser.add_argument("--params", help="params.json 路径（平台 subprocess 模式）")
    parser.add_argument("--patrol-db", help="巡检 SQLite 路径，默认 db/patrol.db")
    parser.add_argument("--devices-db", help="设备 SQLite 路径，默认 db/devices.db")
    parser.add_argument("--templates-dir", help="模板输出目录，默认项目根 templates/")
    parser.add_argument("--vendor", help="仅处理指定厂商")
    parser.add_argument("--model", help="仅处理指定型号")
    parser.add_argument("--command", help="仅处理指定命令")
    parser.add_argument("--max-retries", type=int, default=3, help="验证失败最大重试次数")
    parser.add_argument("--dry-run", action="store_true", help="验证通过但不写模板文件")
    args = parser.parse_args()

    if args.params:
        with open(args.params, encoding="utf-8-sig") as f:
            params = json.load(f)
    else:
        params = {}

    if args.patrol_db:
        params["patrol_db"] = args.patrol_db
    if args.devices_db:
        params["devices_db"] = args.devices_db
    if args.templates_dir:
        params["templates_dir"] = args.templates_dir
    if args.vendor:
        params["vendor"] = args.vendor
    if args.model:
        params["model"] = args.model
    if args.command:
        params["command"] = args.command
    if args.max_retries is not None:
        params["max_retries"] = args.max_retries
    if args.dry_run:
        params["dry_run"] = True

    try:
        result = generate_templates(params)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("success") else 1
    except Exception as exc:
        err = {"success": False, "error": str(exc), "message": str(exc)}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    _configure_stdio_utf8()
    raise SystemExit(main())
