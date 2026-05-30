"""ITSM Skill 脚本路径（平台适配层：仅负责定位 Skill 目录，不含业务逻辑）。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_NAME = "itsm-change-ticket-writer"
SKILL_SCRIPTS_DIR = PROJECT_ROOT / "src" / "skills" / SKILL_NAME / "scripts"
SKILL_LAUNCHER = SKILL_SCRIPTS_DIR / "generate_change_ticket.py"
MAIN_SCRIPT = SKILL_SCRIPTS_DIR / "itsm_change_ticket_excel.py"


def get_change_ticket_script() -> Path:
    if MAIN_SCRIPT.exists():
        return MAIN_SCRIPT
    if SKILL_LAUNCHER.exists():
        return SKILL_LAUNCHER
    raise FileNotFoundError(f"找不到变更工单 Skill 脚本: {MAIN_SCRIPT}")


def get_change_ticket_cwd() -> Path:
    return SKILL_SCRIPTS_DIR
