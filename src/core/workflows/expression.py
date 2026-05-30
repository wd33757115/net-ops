"""Workflow 输入表达式解析：${context.x}、${run.id}、${steps.name.result.y}。"""

from __future__ import annotations

import re
from typing import Any

_EXPR_FULL = re.compile(r"^\$\{([^}]+)\}$")
_EXPR_PARTIAL = re.compile(r"\$\{([^}]+)\}")
# 兼容 WORKFLOW 通知模板中误写为 {context.x} 的形式
_EXPR_BRACE = re.compile(r"\{([a-zA-Z_][\w.]*)\}")


def _lookup(path: str, env: dict[str, Any]) -> Any:
    parts = path.strip().split(".")
    if not parts:
        return None
    cur: Any = env
    for part in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def resolve_value(expr: Any, env: dict[str, Any]) -> Any:
    if not isinstance(expr, str):
        return expr
    text = expr.strip()
    full = _EXPR_FULL.match(text)
    if full:
        return _lookup(full.group(1), env)

    def repl(match: re.Match) -> str:
        val = _lookup(match.group(1), env)
        return "" if val is None else str(val)

    if "${" in text:
        text = _EXPR_PARTIAL.sub(repl, text)
    if _EXPR_BRACE.search(text):
        text = _EXPR_BRACE.sub(repl, text)
    return text


def resolve_inputs(mapping: dict[str, Any], env: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, expr in (mapping or {}).items():
        val = resolve_value(expr, env)
        if val is not None:
            out[key] = val
    return out


def build_step_env(
    *,
    context: dict[str, Any],
    run_id: str,
    ticket_id: str | None,
    step_records: list[Any],
    current_step_index: int,
) -> dict[str, Any]:
    steps_env: dict[str, Any] = {}
    for rec in step_records[:current_step_index]:
        steps_env[rec.step_name] = {
            "result": rec.result or {},
            "artifacts": rec.output_artifacts or {},
        }
    return {
        "context": context or {},
        "run": {"id": run_id, "ticket_id": ticket_id},
        "steps": steps_env,
    }


def step_is_enabled(step_when: str | None, env: dict[str, Any]) -> bool:
    """步骤 when 表达式为真时启用；未配置 when 则始终启用。"""
    if not step_when:
        return True
    return bool(resolve_value(step_when, env))
