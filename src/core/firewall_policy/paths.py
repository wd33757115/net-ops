"""防火墙策略生成脚本路径（Skill scripts 目录）。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_SCRIPTS_DIR = PROJECT_ROOT / "src" / "skills" / "firewall-policy-generator" / "scripts"
SKILL_LAUNCHER = SKILL_SCRIPTS_DIR / "generate_config.py"
MAIN_SCRIPT = SKILL_SCRIPTS_DIR / "firewall-policy.py"
DEFAULT_POLICY_FILE = SKILL_SCRIPTS_DIR / "test_policy.xlsx"
DEFAULT_TOPOLOGY_FILE = SKILL_SCRIPTS_DIR / "topology.json"


def get_firewall_policy_script() -> Path:
    """返回应执行的防火墙策略脚本路径。"""
    if MAIN_SCRIPT.exists():
        return MAIN_SCRIPT
    if SKILL_LAUNCHER.exists():
        return SKILL_LAUNCHER
    raise FileNotFoundError(f"找不到防火墙策略脚本: {MAIN_SCRIPT}")


def get_firewall_policy_cwd() -> Path:
    """subprocess 工作目录（保证 scripts 内相对 import 可用）。"""
    return SKILL_SCRIPTS_DIR
