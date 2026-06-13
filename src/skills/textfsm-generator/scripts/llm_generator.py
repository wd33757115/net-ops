# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""Generate and repair TextFSM templates with the configured LLM."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _ensure_import_path() -> None:
    root = Path(__file__).resolve().parents[4]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def build_generation_prompt(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
    optional_fields: list[str] | None = None,
) -> str:
    optional = ", ".join(optional_fields or []) or "(none)"
    return f"""You are a network CLI TextFSM parser expert.
Create one Python textfsm-compatible template for the samples below.

Vendor: {vendor}
Exact model: {model}
Canonical command: {command}

Required Value names (all must be defined and populated for non-empty output):
{", ".join(required_fields)}

Optional Value names (define and populate when the output contains them):
{optional}

CLI samples:
{cli_output}

Rules:
1. Output only the TextFSM template, without Markdown or explanation.
2. Use only the listed required and optional Value names.
3. Declare values exactly as `Value model (\\S+)`; do not add data types or Value options.
4. Every emitted record must contain every required field; accumulate fields before `-> Record`.
5. Produce stable records suitable for comparing separate patrol runs.
6. Ignore headings, legends, prompts, totals, and process-detail rows unless the requested
   fields need them.
7. A sample may legitimately have no records when it says the feature is not configured.
"""


def build_repair_prompt(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
    optional_fields: list[str] | None,
    current_template: str,
    validation_errors: list[str],
    missing_fields: list[str],
    value_errors: list[str],
) -> str:
    issues = "\n".join(
        [
            *validation_errors,
            *[f"missing field: {field}" for field in missing_fields],
            *[f"invalid value: {error}" for error in value_errors],
        ]
    )
    return (
        build_generation_prompt(
            vendor=vendor,
            model=model,
            command=command,
            cli_output=cli_output,
            required_fields=required_fields,
            optional_fields=optional_fields,
        )
        + f"""

Repair this previous template:
{current_template}

Validation failures:
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
    return str(response.content or "").strip()


def generate_template_text(
    *,
    vendor: str,
    model: str,
    command: str,
    cli_output: str,
    required_fields: list[str],
    optional_fields: list[str] | None = None,
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
            optional_fields=optional_fields,
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
            optional_fields=optional_fields,
        )
    return _strip_fences(call_llm(prompt))


def _strip_fences(text: str) -> str:
    fence = re.search(r"```(?:textfsm|text|)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    return fence.group(1).strip() if fence else text.strip()
