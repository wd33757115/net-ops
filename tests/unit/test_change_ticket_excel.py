"""变更工单 Excel 单元测试（Skill scripts）。"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "src" / "skills" / "itsm-change-ticket-writer" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from change_ticket_excel import build_change_ticket_workbook  # noqa: E402


def test_build_change_ticket_workbook_minimal():
    manifest = {
        "ticket_id": "REQ001",
        "ticket_title": "测试变更",
        "change_background": "背景",
        "change_purpose": "目的",
        "devices": [{"device_name": "FW-01", "vendor": "华为", "ip_address": "10.0.0.1"}],
        "scripts": [
            {
                "device_name": "FW-01",
                "vendor": "华为",
                "order": 1,
                "commands": "acl number 3001\n rule permit ip",
                "command_count": 2,
            }
        ],
        "rollback": [{"step": 1, "device_name": "FW-01", "rollback_command": "undo acl 3001"}],
    }
    data = build_change_ticket_workbook(manifest, workflow_run_id="run-1")
    assert len(data) > 1000
    assert data[:2] == b"PK"
