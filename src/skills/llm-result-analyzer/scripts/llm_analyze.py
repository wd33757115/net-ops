# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""LLM 分析库：汇总上游结果并调用 DeepSeek。"""
from __future__ import annotations

import json
from typing import Any

_MAX_SUMMARY_CHARS = 12000


def load_upstream_payload(params: dict[str, Any]) -> dict[str, Any]:
    """从 Workflow 表达式或 Supervisor depends_on 传入的字段解析上游结果。"""
    if isinstance(params.get("prev_result"), dict):
        return params["prev_result"]
    if isinstance(params.get("upstream_result"), dict):
        return params["upstream_result"]
    # Supervisor v2: {skill-a}_output
    for key, val in params.items():
        if key.endswith("_output") and isinstance(val, dict):
            return val
    if isinstance(params.get("manifest"), dict):
        return {"manifest": params["manifest"]}
    if params.get("devices") or params.get("scripts"):
        return params
    raise ValueError("缺少上游结果：请传入 prev_result / upstream_result / manifest 或 {step}_output")


def build_input_summary(upstream: dict[str, Any], params: dict[str, Any]) -> str:
    """将上游 JSON 压缩为 LLM 可读摘要。"""
    parts: list[str] = []
    ticket_id = params.get("ticket_id") or upstream.get("ticket_id")
    if ticket_id:
        parts.append(f"工单号: {ticket_id}")

    message = upstream.get("message")
    if message:
        parts.append(f"上游消息: {message}")

    manifest = upstream.get("manifest")
    if isinstance(manifest, dict):
        parts.append("--- manifest ---")
        parts.append(json.dumps(manifest, ensure_ascii=False, indent=2))

    data = upstream.get("data")
    if isinstance(data, dict) and data:
        parts.append("--- data ---")
        parts.append(json.dumps(data, ensure_ascii=False, indent=2))

    # 未结构化字段：排除常见元数据后序列化
    skip = {"success", "message", "error", "artifacts", "manifest", "data", "download_url"}
    extra = {k: v for k, v in upstream.items() if k not in skip and v is not None}
    if extra:
        parts.append("--- 其他字段 ---")
        parts.append(json.dumps(extra, ensure_ascii=False, indent=2, default=str))

    text = "\n".join(parts).strip()
    if len(text) > _MAX_SUMMARY_CHARS:
        text = text[:_MAX_SUMMARY_CHARS] + "\n\n[... 上游内容已截断 ...]"
    return text or json.dumps(upstream, ensure_ascii=False, default=str)[:_MAX_SUMMARY_CHARS]


def analyze_with_llm(
    *,
    user_query: str,
    upstream_summary: str,
    analysis_focus: str = "summary",
    ticket_id: str | None = None,
) -> dict[str, Any]:
    from langchain_deepseek import ChatDeepSeek

    from src.common.config import get_settings

    settings = get_settings()
    llm = ChatDeepSeek(
        model=settings.LLM_MODEL,
        temperature=0.2,
        api_key=settings.DEEPSEEK_API_KEY,
        request_timeout=60,
    )

    focus_hint = {
        "summary": "给出简明结论、关键发现与建议行动项（条目化）。",
        "risk": "侧重风险点、影响范围与缓解措施。",
        "compliance": "侧重合规性、变更窗口与审批建议。",
    }.get(analysis_focus, analysis_focus)

    prompt = f"""你是 NetOps 运维分析助手。请基于「上游 Skill 执行结果」回答用户分析问题。
不要编造上游未提供的事实；信息不足时请明确说明。

【分析侧重】{focus_hint}

【用户问题】
{user_query or "请总结上游执行结果并给出运维建议"}

【上游结果摘要】
{upstream_summary}

请用 Markdown 输出，包含：## 结论、## 关键发现、## 建议行动。"""

    if ticket_id:
        prompt += f"\n\n（关联工单: {ticket_id}）"

    response = llm.invoke(prompt)
    text = (response.content or "").strip()
    return {
        "text": text,
        "structured": {"format": "markdown", "sections": ["结论", "关键发现", "建议行动"]},
        "model": settings.LLM_MODEL,
    }
