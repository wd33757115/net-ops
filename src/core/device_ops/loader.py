# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""从 device-backup Skill scripts 目录加载 netops_agent_tools。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEVICE_BACKUP_SCRIPTS = PROJECT_ROOT / "src" / "skills" / "device-backup" / "scripts"


def _ensure_scripts_path() -> None:
    path = str(DEVICE_BACKUP_SCRIPTS)
    if path not in sys.path:
        sys.path.insert(0, path)


def import_netops_agent_tools() -> ModuleType:
    """导入 netops_agent_tools 模块（Skill scripts 目录）。"""
    _ensure_scripts_path()
    import netops_agent_tools

    return netops_agent_tools
