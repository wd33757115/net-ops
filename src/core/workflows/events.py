"""Workflow 进度事件（Redis Pub/Sub，可选降级）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.auth.token_store import get_redis

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "workflow:progress:"


def _channel(run_id: str) -> str:
    return f"{CHANNEL_PREFIX}{run_id}"


def publish_workflow_event(
    run_id: str,
    *,
    step_name: str | None = None,
    skill_name: str | None = None,
    status: str = "running",
    message: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "run_id": run_id,
        "step_name": step_name,
        "skill_name": skill_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    client = get_redis()
    if not client:
        logger.debug("Redis 不可用，跳过 workflow 事件: %s", payload)
        return
    try:
        client.publish(_channel(run_id), json.dumps(payload, ensure_ascii=False))
        client.publish("workflow:progress:all", json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning("发布 workflow 事件失败: %s", exc)
