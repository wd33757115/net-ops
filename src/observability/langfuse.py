"""Langfuse 追踪封装（兼容自托管 Langfuse v2 + Python SDK v2）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.auth.models import CurrentUser
from src.common.config import get_settings

logger = logging.getLogger(__name__)

_langfuse_client: Any | None = None


def is_langfuse_enabled() -> bool:
    settings = get_settings()
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def get_langfuse_client() -> Any | None:
    """获取 Langfuse v2 客户端单例。"""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not is_langfuse_enabled():
        return None

    settings = get_settings()
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST or "http://localhost:3001",
        )
        return _langfuse_client
    except Exception as exc:
        logger.warning("Langfuse client init failed: %s", exc)
        return None


def _build_metadata(
    *,
    user: CurrentUser | None,
    thread_id: str,
    conversation_id: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "conversation_id": conversation_id,
        "graph_thread_id": thread_id,
    }
    if user:
        metadata.update(
            {
                "username": user.username,
                "role": user.role,
                "thread_prefix": user.thread_prefix,
                "can_view_trace_detail": user.can_view_trace_detail(),
            }
        )
    return metadata


@dataclass
class LangfuseChatTrace:
    client: Any
    trace: Any
    node_spans: dict[str, Any] = field(default_factory=dict)

    @property
    def trace_id(self) -> str | None:
        trace_id = getattr(self.trace, "id", None)
        return str(trace_id) if trace_id else None


def start_chat_trace(
    *,
    user: CurrentUser | None,
    thread_id: str,
    conversation_id: str,
    trace_name: str = "supervisor_v2_chat",
    query: str | None = None,
) -> LangfuseChatTrace | None:
    """创建 Langfuse trace；未配置密钥时返回 None。"""
    client = get_langfuse_client()
    if not client:
        return None

    try:
        trace = client.trace(
            name=trace_name,
            user_id=user.user_id if user else None,
            session_id=thread_id,
            metadata=_build_metadata(
                user=user,
                thread_id=thread_id,
                conversation_id=conversation_id,
            ),
            input={"query": query} if query else None,
        )
        return LangfuseChatTrace(client=client, trace=trace)
    except Exception as exc:
        logger.warning("Langfuse trace start failed: %s", exc)
        return None


def record_graph_node(
    lf_trace: LangfuseChatTrace | None,
    node_name: str,
    summary: dict[str, Any],
) -> None:
    if not lf_trace:
        return
    try:
        span = lf_trace.trace.span(name=node_name, metadata=summary)
        span.end(output=summary)
        lf_trace.node_spans[node_name] = span
    except Exception as exc:
        logger.debug("Langfuse node span failed for %s: %s", node_name, exc)


def end_chat_trace(
    lf_trace: LangfuseChatTrace | None,
    *,
    output: Any | None = None,
    error: str | None = None,
) -> None:
    if not lf_trace:
        return
    try:
        if error:
            lf_trace.trace.update(output={"error": error}, level="ERROR")
        elif output is not None:
            lf_trace.trace.update(output=output)
    except Exception as exc:
        logger.warning("Langfuse trace update failed: %s", exc)
    finally:
        flush_langfuse(lf_trace.client)


def flush_langfuse(client: Any | None = None) -> None:
    target = client or get_langfuse_client()
    if not target:
        return
    try:
        target.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)


def get_trace_url(trace_id: str | None) -> str | None:
    if not trace_id or not is_langfuse_enabled():
        return None
    host = (get_settings().LANGFUSE_HOST or "http://localhost:3001").rstrip("/")
    return f"{host}/trace/{trace_id}"


def get_langfuse_handler(**kwargs: Any) -> LangfuseChatTrace | None:
    """兼容旧调用方：等价于 start_chat_trace。"""
    return start_chat_trace(**kwargs)
