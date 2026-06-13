# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Load TextFSM generator configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATEGORIES = SKILL_ROOT / "config" / "command_categories.yaml"
DEFAULT_MAPPING = SKILL_ROOT / "config" / "command_mapping.yaml"
DEFAULT_SIGNATURES = SKILL_ROOT / "config" / "device_signatures.yaml"
DEFAULT_ALIASES = SKILL_ROOT / "config" / "command_aliases.yaml"


@dataclass(frozen=True)
class CategorySpec:
    name: str
    required_fields: list[str]
    optional_fields: list[str]
    entity_type: str
    primary_keys: list[str]
    validators: dict[str, dict[str, Any]]
    allow_empty: bool = False
    empty_patterns: list[str] | None = None
    ignore_fields: list[str] | None = None

    @property
    def fields(self) -> list[str]:
        return [*self.required_fields, *self.optional_fields]


@dataclass(frozen=True)
class CommandMapping:
    vendor: str
    model: str
    command: str
    category: str
    family: str | None = None


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"configuration file does not exist: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return data


def load_categories(path: Path | None = None) -> dict[str, CategorySpec]:
    raw = load_yaml(path or DEFAULT_CATEGORIES)
    output: dict[str, CategorySpec] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        output[str(name)] = CategorySpec(
            name=str(name),
            required_fields=list(spec.get("required_fields") or spec.get("fields") or []),
            optional_fields=list(spec.get("optional_fields") or []),
            entity_type=str(spec.get("entity_type") or name),
            primary_keys=list(spec.get("primary_keys") or []),
            validators=dict(spec.get("validators") or {}),
            allow_empty=bool(spec.get("allow_empty", False)),
            empty_patterns=list(spec.get("empty_patterns") or []),
            ignore_fields=list(spec.get("ignore_fields") or []),
        )
    return output


def load_command_mapping(path: Path | None = None) -> list[CommandMapping]:
    raw = load_yaml(path or DEFAULT_MAPPING)
    mappings: list[CommandMapping] = []
    for device_key, commands in raw.items():
        if not isinstance(commands, dict):
            continue
        parts = str(device_key).strip().split(None, 1)
        if len(parts) != 2:
            continue
        vendor, model = parts
        for command, meta in commands.items():
            if not isinstance(meta, dict):
                continue
            category = str(meta.get("category") or "").strip()
            if category:
                mappings.append(
                    CommandMapping(
                        vendor=vendor,
                        model=model,
                        command=normalize_command(str(command)),
                        category=category,
                        family=str(meta.get("family") or "").strip() or None,
                    )
                )
    return mappings


def load_command_aliases(path: Path | None = None) -> dict[str, str]:
    raw = load_yaml(path or DEFAULT_ALIASES)
    aliases = raw.get("aliases", raw)
    if not isinstance(aliases, dict):
        return {}
    return {
        normalize_command(str(alias)): normalize_command(str(canonical))
        for alias, canonical in aliases.items()
        if str(alias).strip() and str(canonical).strip()
    }


def load_device_signatures(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_SIGNATURES)


def normalize_command(command: str, aliases: dict[str, str] | None = None) -> str:
    normalized = " ".join(str(command or "").strip().lower().split())
    if normalized.startswith("dis "):
        normalized = f"display {normalized[4:]}"
    return (aliases or {}).get(normalized, normalized)


def list_device_profiles(mappings: list[CommandMapping]) -> list[str]:
    return sorted({f"{item.vendor} {item.model}" for item in mappings})


def resolve_device_mapping(
    device_model: str,
    mappings: list[CommandMapping],
) -> tuple[str, str] | None:
    normalized = str(device_model or "").strip()
    for item in mappings:
        if normalized in {item.model, f"{item.vendor} {item.model}"}:
            return item.vendor, item.model
    return None


def find_category(
    vendor: str,
    model: str,
    command: str,
    mappings: list[CommandMapping],
) -> str | None:
    normalized = normalize_command(command)
    for item in mappings:
        if (
            item.vendor.lower() == vendor.lower()
            and item.model.lower() == model.lower()
            and item.command == normalized
        ):
            return item.category
    return None


def resolve_category(
    vendor: str,
    model: str,
    command: str,
    mappings: list[CommandMapping],
    *,
    explicit_category: str | None = None,
) -> str | None:
    if explicit_category and explicit_category.strip():
        return explicit_category.strip()
    category = find_category(vendor, model, command, mappings)
    if category:
        return category
    if model.lower() != "generic":
        return find_category(vendor, "Generic", command, mappings)
    return None


def required_fields_for_category(
    category: str,
    categories: dict[str, CategorySpec],
) -> list[str]:
    spec = categories.get(category)
    return list(spec.required_fields) if spec else []
