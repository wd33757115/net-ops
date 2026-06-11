# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""用 LLM 从自然语言话术中语义提取 vendor / model（非硬编码关键词）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def build_extract_prompt(
    text: str,
    *,
    known_devices: list[str] | None = None,
    command: str | None = None,
) -> str:
    devices_block = (
        "\n".join(f"- {item}" for item in (known_devices or [])[:40])
        or "(配置中暂无参考档案，请按行业常识归一化)"
    )
    cmd_hint = command or "未知"
    return f"""你是网络设备运维助手。请从用户输入中理解并提取设备厂商 vendor 与型号 model。

要求:
1. 理解自然语义，不要依赖固定句式；例如「华三」「新华三」「H3C 核心」均归一化为 vendor=H3C
2. model 只填型号（如 S5590、CE12800），不要重复 vendor
3. 用户未明确提及则对应字段填 null，不要猜测
4. 可参考下列已知设备档案的拼写，但档案未覆盖时仍按用户语义输出
5. CLI 命令（若已识别）: {cmd_hint}

已知设备档案（vendor model）:
{devices_block}

用户输入:
{text[:6000]}

只输出 JSON，不要 Markdown:
{{"vendor": "H3C 或 null", "model": "S5590 或 null"}}"""


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group())
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def _normalize_field(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "unknown", "未知", "无"}:
        return None
    return text


def extract_device_context(
    text: str,
    *,
    known_devices: list[str] | None = None,
    command: str | None = None,
) -> tuple[str | None, str | None]:
    """
    语义提取 vendor/model。无 API Key 或 LLM 失败时返回 (None, None)。
    """
    text = (text or "").strip()
    if not text:
        return None, None

    try:
        from llm_generator import call_llm

        prompt = build_extract_prompt(text, known_devices=known_devices, command=command)
        raw = call_llm(prompt)
        data = _parse_json_object(raw)
        vendor = _normalize_field(data.get("vendor"))
        model = _normalize_field(data.get("model"))
        if vendor or model:
            logger.info("semantic_extract vendor=%s model=%s", vendor, model)
        return vendor, model
    except Exception as exc:
        logger.warning("semantic_extract 失败，将使用后续兜底: %s", exc)
        return None, None
