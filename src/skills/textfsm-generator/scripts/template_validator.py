# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""TextFSM 四层验证：编译 → 解析 → 字段 → 值合法性。"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import textfsm
except ImportError:  # pragma: no cover
    textfsm = None  # type: ignore[assignment]


@dataclass
class ValidationResult:
    compile_success: bool = False
    parse_success: bool = False
    record_count: int = 0
    field_coverage: int = 0
    validation_score: int = 0
    missing_fields: list[str] = field(default_factory=list)
    value_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return (
            self.compile_success
            and self.parse_success
            and self.record_count > 0
            and not self.missing_fields
            and not self.value_errors
        )


def _parse_percent(value: Any) -> float | None:
    text = str(value).strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


def validate_field_values(
    records: list[dict[str, Any]],
    validators: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for field_name, rules in validators.items():
        rule_type = rules.get("type")
        for idx, rec in enumerate(records):
            if field_name not in rec:
                continue
            raw = rec[field_name]
            if rule_type == "percent":
                num = _parse_percent(raw)
                if num is None:
                    errors.append(f"record[{idx}].{field_name}={raw!r} 非数值")
                elif not 0 <= num <= 100:
                    errors.append(f"record[{idx}].{field_name}={raw!r} 超出 0-100")
            elif rule_type == "enum":
                allowed = {str(v).strip().lower() for v in (rules.get("values") or [])}
                if allowed and str(raw).strip().lower() not in allowed:
                    errors.append(f"record[{idx}].{field_name}={raw!r} 不在允许值 {sorted(allowed)}")
    return errors


def check_required_fields(records: list[dict[str, Any]], required_fields: list[str]) -> tuple[int, list[str]]:
    if not required_fields:
        return 100, []
    if not records:
        return 0, list(required_fields)
    keys: set[str] = set()
    for rec in records:
        keys.update(rec.keys())
    missing = [f for f in required_fields if f not in keys]
    coverage = int(round(100 * (len(required_fields) - len(missing)) / len(required_fields)))
    return coverage, missing


def parse_with_template(template_text: str, cli_output: str) -> tuple[list[dict[str, Any]], list[str]]:
    if textfsm is None:
        return [], ["textfsm 模块未安装"]
    try:
        fsm = textfsm.TextFSM(io.StringIO(template_text))
        rows = fsm.ParseText(cli_output)
        headers = fsm.header
        records = [dict(zip(headers, row)) for row in rows]
        return records, []
    except Exception as exc:
        return [], [f"解析失败: {exc}"]


def compile_template(template_text: str) -> tuple[bool, list[str]]:
    if textfsm is None:
        return False, ["textfsm 模块未安装"]
    try:
        textfsm.TextFSM(io.StringIO(template_text))
        return True, []
    except Exception as exc:
        return False, [f"编译失败: {exc}"]


def validate_template(
    template_text: str,
    cli_output: str,
    required_fields: list[str],
    validators: dict[str, dict[str, Any]] | None = None,
) -> ValidationResult:
    result = ValidationResult()
    validators = validators or {}

    ok, compile_errors = compile_template(template_text)
    result.compile_success = ok
    result.errors.extend(compile_errors)
    if not ok:
        result.validation_score = 0
        return result

    records, parse_errors = parse_with_template(template_text, cli_output)
    result.errors.extend(parse_errors)
    if parse_errors:
        result.validation_score = 25
        return result

    result.record_count = len(records)
    result.records = records
    result.parse_success = len(records) > 0
    if not result.parse_success:
        result.errors.append("解析记录数为 0")
        result.validation_score = 25
        return result

    coverage, missing = check_required_fields(records, required_fields)
    result.field_coverage = coverage
    result.missing_fields = missing

    value_errors = validate_field_values(records, validators)
    result.value_errors = value_errors
    result.errors.extend(value_errors)

    score = 25  # compile
    score += 25  # parse
    score += int(round(25 * coverage / 100))
    if not value_errors:
        score += 25
    else:
        score += max(0, 25 - len(value_errors) * 5)
    result.validation_score = min(100, score)
    return result


def strip_llm_template(raw: str) -> str:
    """去除 LLM 可能输出的 Markdown 围栏与解释性前后缀。"""
    text = (raw or "").strip()
    fence = re.search(r"```(?:textfsm|text|)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    lines = text.splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started:
            if line.strip().startswith("Value ") or line.strip().startswith("Start"):
                started = True
            else:
                continue
        out.append(line)
    if out:
        return "\n".join(out).strip() + "\n"
    return text.strip() + "\n"
