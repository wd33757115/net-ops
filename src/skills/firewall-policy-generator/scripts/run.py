#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""防火墙策略 Skill 统一 CLI 入口（--params JSON + --output-dir）。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# 复用 Skill 内 manifest 构建（自包含，不依赖 core）
from manifest import build_manifest_from_output, write_manifest_file  # noqa: E402

MAIN_SCRIPT = SCRIPT_DIR / "firewall-policy.py"
DEFAULT_TOPOLOGY = SCRIPT_DIR / "topology.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="防火墙策略生成 Skill")
    parser.add_argument("--params", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--policy", help="策略 Excel 本地路径（覆盖 params.policy_file_url）")
    parser.add_argument("--zip", help="兼容参数，未使用")
    args = parser.parse_args()

    with open(args.params, encoding="utf-8-sig") as f:
        p = json.load(f)

    ticket_id = (p.get("ticket_id") or "").strip() or f"POLICY_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        policy_path = args.policy or p.get("policy_file_url") or p.get("_policy_path")
        if not policy_path or not os.path.exists(str(policy_path)):
            default = SCRIPT_DIR / "policies.xlsx"
            if not default.exists():
                default = SKILL_ROOT.parent / "firewall-policy-generator" / "scripts" / "policies.xlsx"
            policy_path = str(default) if default.exists() else None
        if not policy_path:
            print(json.dumps({"success": False, "error": "未提供策略文件"}, ensure_ascii=False), file=sys.stderr)
            return 1

        policy_copy = os.path.join(tmpdir, f"policy_{ticket_id}.xlsx")
        shutil.copy(str(policy_path), policy_copy)

        topology = p.get("topology_file_url") or str(DEFAULT_TOPOLOGY)
        if not os.path.exists(str(topology)):
            topology = str(DEFAULT_TOPOLOGY)

        cmd = [
            sys.executable,
            str(MAIN_SCRIPT),
            "-t",
            str(topology),
            "-p",
            policy_copy,
            "-o",
            args.output_dir,
            "-u",
            p.get("requester") or "system",
            "--ticket-id",
            ticket_id,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(SCRIPT_DIR))
        if proc.returncode != 0:
            err = {"success": False, "error": proc.stderr or proc.stdout or "策略生成失败"}
            print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
            return 1

        manifest = build_manifest_from_output(
            args.output_dir,
            ticket_id=ticket_id,
            ticket_title=p.get("ticket_title", "防火墙策略生成"),
            change_background=p.get("change_background") or p.get("ticket_title", ""),
            change_purpose=p.get("change_purpose") or "开通防火墙策略",
            requester=p.get("requester", ""),
            requester_dept=p.get("requester_dept", ""),
            assignee=p.get("assignee", ""),
            priority=p.get("priority", "P2"),
            due_date=p.get("due_date"),
            topology_path=str(topology),
            trace_id=p.get("workflow_run_id"),
        )
        write_manifest_file(args.output_dir, manifest)

        zip_name = f"firewall_policies_{ticket_id}.zip"
        zip_base = os.path.join(tmpdir, zip_name.replace(".zip", ""))
        shutil.make_archive(zip_base, "zip", args.output_dir)
        zip_path = zip_base + ".zip"

        result = {
            "success": True,
            "status": "success",
            "message": "防火墙策略生成成功",
            "ticket_id": ticket_id,
            "filename": zip_name,
            "manifest": manifest,
            "_local_zip": zip_path,
        }
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
