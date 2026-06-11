# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""调用 LLM 生成 / 修复 TextFSM 模板。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _ensure_import_path() -> None:
    root = _project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def build_generation_prompt(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
) -> str:
    fields_text = ", ".join(required_fields)
    return f"""你是网络设备 CLI TextFSM 模板专家。请为下列设备命令编写标准 TextFSM 模板（Python textfsm 库语法）。

设备厂商: {vendor}
设备型号: {model}
命令: {command}

必须提取字段（Value 名称必须完全一致，不得增删）:
{fields_text}

CLI 输出样例:
{cli_output}

硬性要求:
1. 只输出 TextFSM 模板正文，不要任何解释
2. 不要使用 Markdown，不要输出 ``` 代码块
3. 使用标准 TextFSM 语法: Value 定义 + Start 状态 + 正则规则
4. 每个必填字段必须有对应 Value 定义
5. 确保样例输出可被模板解析且 record 数 > 0
"""


def build_repair_prompt(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
    current_template: str,
    validation_errors: list[str],
    missing_fields: list[str],
    value_errors: list[str],
) -> str:
    base = build_generation_prompt(
        vendor=vendor,
        model=model,
        command=command,
        cli_output=cli_output,
        required_fields=required_fields,
    )
    issues = "\n".join(
        [
            *validation_errors,
            *[f"缺失字段: {f}" for f in missing_fields],
            *[f"非法字段值: {e}" for e in value_errors],
        ]
    )
    return (
        base
        + f"""

上一版模板验证失败，请修复后重新输出完整模板。

当前模板:
{current_template}

验证错误:
{issues}
"""
    )


def call_llm(prompt: str) -> str:
    _ensure_import_path()
    from langchain_deepseek import ChatDeepSeek

    from src.common.config import get_settings

    settings = get_settings()
    llm = ChatDeepSeek(
        model=settings.LLM_MODEL,
        temperature=0.1,
        api_key=settings.DEEPSEEK_API_KEY,
        request_timeout=120,
    )
    response = llm.invoke(prompt)
    return (response.content or "").strip()


def generate_template_text(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
    previous_template: str | None = None,
    validation_errors: list[str] | None = None,
    missing_fields: list[str] | None = None,
    value_errors: list[str] | None = None,
) -> str:
    if previous_template:
        prompt = build_repair_prompt(
            vendor=vendor,
            model=model,
            command=command,
            cli_output=cli_output,
            required_fields=required_fields,
            current_template=previous_template,
            validation_errors=validation_errors or [],
            missing_fields=missing_fields or [],
            value_errors=value_errors or [],
        )
    else:
        prompt = build_generation_prompt(
            vendor=vendor,
            model=model,
            command=command,
            cli_output=cli_output,
            required_fields=required_fields,
        )
    raw = call_llm(prompt)
    return _strip_fences(raw)


def _strip_fences(text: str) -> str:
    fence = re.search(r"```(?:textfsm|text|)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text.strip()
