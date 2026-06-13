# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Shared TextFSM asset paths and lookup helpers."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_TEXTFSM_ROOT = PROJECT_ROOT / "src" / "skills" / "shared" / "textfsm-templates"
LEGACY_TEXTFSM_ROOT = PROJECT_ROOT / "templates"
MANIFEST_NAME = "manifest.json"


def safe_slug(value: str) -> str:
    """Return a stable cross-platform directory/file component."""
    normalized = re.sub(r"\s+", "_", str(value or "").strip())
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("._")
    return normalized or "Generic"


def command_template_name(command: str) -> str:
    return f"{safe_slug(str(command or '').strip().lower())}.textfsm"


def template_path(root: str | Path, model: str, command: str) -> Path:
    return Path(root) / safe_slug(model) / command_template_name(command)


def resolve_textfsm_template(
    *,
    model: str,
    command: str,
    family: str | None = None,
    shared_root: str | Path | None = None,
    legacy_root: str | Path | None = None,
) -> Path | None:
    """Resolve exact-model, family, then legacy templates in that order."""
    shared = Path(shared_root or SHARED_TEXTFSM_ROOT)
    legacy = Path(legacy_root or LEGACY_TEXTFSM_ROOT)
    candidates = [template_path(shared, model, command)]
    if family and safe_slug(family) != safe_slug(model):
        candidates.append(template_path(shared, family, command))
    candidates.append(template_path(legacy, model, command))
    if family and safe_slug(family) != safe_slug(model):
        candidates.append(template_path(legacy, family, command))
    return next((path for path in candidates if path.is_file()), None)


def discover_textfsm_templates(
    *,
    model: str,
    shared_root: str | Path | None = None,
    legacy_root: str | Path | None = None,
) -> dict[str, Path]:
    """Return a filename map with shared exact-model assets taking precedence."""
    shared = Path(shared_root or SHARED_TEXTFSM_ROOT)
    legacy = Path(legacy_root or LEGACY_TEXTFSM_ROOT)
    manifest = load_manifest(shared)
    family = next(
        (
            str(item.get("family"))
            for item in manifest.get("templates") or []
            if item.get("model") == model and item.get("family")
        ),
        None,
    )
    directories = [legacy / safe_slug(model)]
    if family:
        directories.append(shared / safe_slug(family))
    directories.append(shared / safe_slug(model))
    mapping: dict[str, Path] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() == ".textfsm":
                mapping[path.name] = path
    return mapping


def atomic_write_text(path: str | Path, content: str) -> Path:
    """Atomically replace a UTF-8 text asset."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def load_manifest(root: str | Path | None = None) -> dict[str, Any]:
    path = Path(root or SHARED_TEXTFSM_ROOT) / MANIFEST_NAME
    if not path.is_file():
        return {"schema_version": 1, "templates": []}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {"schema_version": 1, "templates": []}


def upsert_manifest_entry(
    entry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> Path:
    shared = Path(root or SHARED_TEXTFSM_ROOT)
    manifest = load_manifest(shared)
    templates = list(manifest.get("templates") or [])
    key = (entry.get("vendor"), entry.get("model"), entry.get("command"))
    templates = [
        item
        for item in templates
        if (item.get("vendor"), item.get("model"), item.get("command")) != key
    ]
    templates.append(entry)
    templates.sort(
        key=lambda item: (
            str(item.get("vendor") or ""),
            str(item.get("model") or ""),
            str(item.get("command") or ""),
        )
    )
    manifest["schema_version"] = 1
    manifest["templates"] = templates
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return atomic_write_text(shared / MANIFEST_NAME, payload)


def remove_manifest_entry(
    *,
    vendor: str,
    model: str,
    command: str,
    root: str | Path | None = None,
) -> Path:
    shared = Path(root or SHARED_TEXTFSM_ROOT)
    manifest = load_manifest(shared)
    manifest["templates"] = [
        item
        for item in manifest.get("templates") or []
        if (item.get("vendor"), item.get("model"), item.get("command"))
        != (vendor, model, command)
    ]
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return atomic_write_text(shared / MANIFEST_NAME, payload)
