# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""ITSM 防火墙变更 Workflow 端到端测试（Webhook 触发）。"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "src/skills/firewall-policy-generator/scripts/policies.xlsx"
BASE = "http://localhost:8000"


def main() -> int:
    ticket_id = f"E2E-WF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payload = {
        "ticket_id": ticket_id,
        "ticket_title": "E2E ITSM防火墙变更闭环测试",
        "service_catalog": "安全-防火墙策略开通",
        "requester": "test.user",
        "requester_dept": "测试部",
        "assignee": "admin",
        "priority": "P2",
        "due_date": "2026-05-24",
        "policy_file": {"url": str(POLICY), "filename": "policies.xlsx"},
        "callback_url": f"{BASE}/api/v1/itsm/webhook/callback",
        "callback_headers": {"X-API-Key": "itsm_callback_key_123"},
    }

    print(f"POST {BASE}/api/v1/itsm/webhook/firewall-policy")
    resp = requests.post(f"{BASE}/api/v1/itsm/webhook/firewall-policy", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    run_id = data["workflow_run_id"]
    print(f"workflow_run_id={run_id}")

    deadline = time.time() + 600
    final = None
    while time.time() < deadline:
        time.sleep(8)
        wf = requests.get(f"{BASE}/api/v1/workflows/{run_id}", timeout=30).json()
        steps = " | ".join(f"{s['step_name']}:{s['status']}" for s in wf.get("steps", []))
        print(f"workflow={wf.get('status')} steps=[{steps}]")
        if wf.get("status") in ("completed", "failed", "cancelled"):
            final = wf
            break

    if not final:
        print("FAIL: timeout")
        return 1
    if final.get("status") != "completed":
        print(f"FAIL: {final.get('error_message')}")
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return 1

    for step in final.get("steps", []):
        arts = step.get("output_artifacts") or {}
        if zip_art := arts.get("config_zip"):
            print(f"ZIP: {zip_art.get('download_url')}")
        if excel := arts.get("change_excel"):
            print(f"Excel: {excel.get('download_url')}")

    print("E2E PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
