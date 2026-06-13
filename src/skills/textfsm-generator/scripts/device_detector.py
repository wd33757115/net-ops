# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Deterministic vendor/model detection for offline patrol captures."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config_loader import normalize_command


@dataclass(frozen=True)
class DeviceIdentity:
    vendor: str | None
    model: str | None
    family: str | None
    confidence: float
    evidence_command: str | None
    evidence_text: str | None
    source: str

    @property
    def detected(self) -> bool:
        return bool(self.vendor and self.model)


def family_for(vendor: str, model: str, config: dict[str, Any]) -> str | None:
    for item in config.get("families") or []:
        if str(item.get("vendor") or "").lower() != vendor.lower():
            continue
        if any(
            re.search(str(pattern), model, re.IGNORECASE)
            for pattern in item.get("model_patterns") or []
        ):
            return str(item.get("family") or "").strip() or None
    return None


def _normalize_model(model: str, config: dict[str, Any]) -> str:
    value = model.strip().strip(",")
    for item in config.get("normalization") or []:
        pattern = str(item.get("pattern") or "")
        if pattern and re.search(pattern, value, re.IGNORECASE):
            value = re.sub(
                pattern,
                str(item.get("replacement") or ""),
                value,
                flags=re.IGNORECASE,
            )
    return value


def _match_rules(blocks: Iterable[Any], config: dict[str, Any]) -> DeviceIdentity | None:
    by_command: dict[str, list[Any]] = {}
    for block in blocks:
        by_command.setdefault(normalize_command(block.command_canonical), []).append(block)
    for rule in config.get("detection_rules") or []:
        command = normalize_command(str(rule.get("command") or ""))
        pattern = str(rule.get("pattern") or "")
        for block in by_command.get(command, []):
            match = re.search(pattern, block.raw_output, re.IGNORECASE | re.MULTILINE)
            if not match:
                continue
            model = match.groupdict().get("model") or str(rule.get("model") or "")
            vendor = str(rule.get("vendor") or "").strip()
            if not vendor or not model:
                continue
            normalized_model = _normalize_model(model, config)
            return DeviceIdentity(
                vendor=vendor,
                model=normalized_model,
                family=family_for(vendor, normalized_model, config),
                confidence=float(rule.get("confidence") or 0.95),
                evidence_command=command,
                evidence_text=match.group(0).strip()[:500],
                source="command_output",
            )
    return None


def _filename_hint(path: Path, config: dict[str, Any]) -> DeviceIdentity | None:
    for item in config.get("filename_hints") or []:
        pattern = str(item.get("pattern") or "")
        if not pattern or not re.search(pattern, path.name, re.IGNORECASE):
            continue
        vendor = str(item.get("vendor") or "").strip()
        model = str(item.get("model") or "").strip()
        if vendor and model:
            return DeviceIdentity(
                vendor=vendor,
                model=model,
                family=family_for(vendor, model, config),
                confidence=float(item.get("confidence") or 0.55),
                evidence_command=None,
                evidence_text=path.name,
                source="filename",
            )
    return None


def detect_device_identity(
    *,
    path: Path,
    blocks: Iterable[Any],
    config: dict[str, Any],
    vendor: str | None = None,
    model: str | None = None,
) -> DeviceIdentity:
    if vendor and model:
        return DeviceIdentity(
            vendor=vendor.strip(),
            model=model.strip(),
            family=family_for(vendor.strip(), model.strip(), config),
            confidence=1.0,
            evidence_command=None,
            evidence_text="explicit parameters",
            source="explicit",
        )
    detected = _match_rules(blocks, config)
    if detected:
        return detected
    hinted = _filename_hint(path, config)
    if hinted:
        return hinted
    return DeviceIdentity(
        vendor=vendor.strip() if vendor else None,
        model=model.strip() if model else None,
        family=None,
        confidence=0.0,
        evidence_command=None,
        evidence_text=None,
        source="unresolved",
    )
