# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""加载 command_categories / command_mapping 配置。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATEGORIES = SKILL_ROOT / "config" / "command_categories.yaml"
DEFAULT_MAPPING = SKILL_ROOT / "config" / "command_mapping.yaml"


@dataclass(frozen=True)
class CategorySpec:
    name: str
    fields: list[str]
    validators: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class CommandMapping:
    vendor: str
    model: str
    command: str
    category: str


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误: {path}")
    return data


def load_categories(path: Path | None = None) -> dict[str, CategorySpec]:
    raw = load_yaml(path or DEFAULT_CATEGORIES)
    out: dict[str, CategorySpec] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        fields = list(spec.get("fields") or [])
        validators = dict(spec.get("validators") or {})
        out[str(name)] = CategorySpec(name=str(name), fields=fields, validators=validators)
    return out


def load_command_mapping(path: Path | None = None) -> list[CommandMapping]:
    raw = load_yaml(path or DEFAULT_MAPPING)
    mappings: list[CommandMapping] = []
    for device_key, commands in raw.items():
        if not isinstance(commands, dict):
            continue
        parts = str(device_key).strip().split(None, 1)
        if len(parts) != 2:
            continue
        vendor, model = parts[0], parts[1]
        for command, meta in commands.items():
            if not isinstance(meta, dict):
                continue
            category = str(meta.get("category") or "").strip()
            if not category:
                continue
            mappings.append(
                CommandMapping(
                    vendor=vendor,
                    model=model,
                    command=str(command).strip(),
                    category=category,
                )
            )
    return mappings


def list_device_profiles(mappings: list[CommandMapping]) -> list[str]:
    """从 mapping 配置动态列出已知 vendor model 档案（供 LLM 参考，非硬编码规则）。"""
    seen: set[str] = set()
    profiles: list[str] = []
    for item in mappings:
        key = f"{item.vendor} {item.model}"
        if key in seen:
            continue
        seen.add(key)
        profiles.append(key)
    return sorted(profiles)


def resolve_device_mapping(device_model: str, mappings: list[CommandMapping]) -> tuple[str, str] | None:
    """将 devices.model 解析为 (vendor, model)。"""
    model_norm = (device_model or "").strip()
    if not model_norm:
        return None
    for m in mappings:
        if model_norm == m.model or model_norm == f"{m.vendor} {m.model}":
            return m.vendor, m.model
    return None


def find_category(
    vendor: str,
    model: str,
    command: str,
    mappings: list[CommandMapping],
) -> str | None:
    cmd_norm = command.strip()
    for m in mappings:
        if m.vendor == vendor and m.model == model and m.command == cmd_norm:
            return m.category
    return None


def resolve_category(
    vendor: str,
    model: str,
    command: str,
    mappings: list[CommandMapping],
    *,
    explicit_category: str | None = None,
) -> str | None:
    """解析 category：显式参数 → 精确 mapping → Generic 型号 → 命令关键词推断。"""
    if explicit_category:
        cat = explicit_category.strip()
        return cat or None

    cat = find_category(vendor, model, command, mappings)
    if cat:
        return cat

    if model != "Generic":
        cat = find_category(vendor, "Generic", command, mappings)
        if cat:
            return cat

    cmd_l = command.strip().lower()
    if "fan" in cmd_l:
        return "fan"
    if "cpu" in cmd_l:
        return "cpu"
    if "memory" in cmd_l or "mem" in cmd_l:
        return "memory"
    if "interface" in cmd_l:
        return "interface"
    return None


def required_fields_for_category(category: str, categories: dict[str, CategorySpec]) -> list[str]:
    spec = categories.get(category)
    if not spec:
        return []
    return list(spec.fields)
