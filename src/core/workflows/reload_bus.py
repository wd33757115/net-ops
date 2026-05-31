"""Workflow 插件跨进程热重载（Redis Pub/Sub）。"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Callable

from src.auth.token_store import get_redis

logger = logging.getLogger(__name__)

RELOAD_CHANNEL = "workflow:reload"
_listener_thread: threading.Thread | None = None
_stop_event = threading.Event()


def reload_all_registries(*, source: str = "local") -> dict[str, int]:
    """在当前进程重载 Workflow / Chat Intent / Webhook 注册表。"""
    from src.core.plugins.chat_intent import get_chat_intent_registry
    from src.core.plugins.itsm_webhook import get_itsm_webhook_registry
    from src.core.workflows.registry import load_workflows

    wf_count = len(load_workflows(force=True))
    get_chat_intent_registry().load(force=True)
    intent_count = len(get_chat_intent_registry().all_intents())
    get_itsm_webhook_registry().load(force=True)
    logger.info("Workflow 注册表已重载 source=%s templates=%s intents=%s", source, wf_count, intent_count)
    return {"templates": wf_count, "intents": intent_count}


def publish_workflow_reload(*, source: str = "api", plugin_name: str | None = None) -> bool:
    """广播重载信号到所有订阅进程（Gateway / Celery Worker）。"""
    client = get_redis()
    if not client:
        logger.debug("Redis 不可用，仅本地重载")
        reload_all_registries(source=source)
        return False
    payload = {
        "source": source,
        "plugin_name": plugin_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.publish(RELOAD_CHANNEL, json.dumps(payload, ensure_ascii=False))
        return True
    except Exception as exc:
        logger.warning("发布 workflow reload 失败: %s", exc)
        reload_all_registries(source=source)
        return False


def broadcast_workflow_reload(*, source: str = "api", plugin_name: str | None = None) -> dict[str, int]:
    """本地重载 + 广播到其他 worker。"""
    stats = reload_all_registries(source=source)
    publish_workflow_reload(source=source, plugin_name=plugin_name)
    return stats


def _listen_loop(on_reload: Callable[[dict], None] | None = None) -> None:
    client = get_redis()
    if not client:
        logger.warning("Redis 不可用，跳过多 worker reload 监听")
        return
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    try:
        pubsub.subscribe(RELOAD_CHANNEL)
        logger.info("已订阅 Workflow 热重载频道: %s", RELOAD_CHANNEL)
        while not _stop_event.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "message":
                continue
            try:
                payload = json.loads(message["data"])
            except Exception:
                payload = {"source": "unknown"}
            reload_all_registries(source=str(payload.get("source") or "pubsub"))
            if on_reload:
                on_reload(payload)
    except Exception as exc:
        if not _stop_event.is_set():
            logger.warning("Workflow reload 监听异常: %s", exc)
    finally:
        try:
            pubsub.close()
        except Exception:
            pass


def start_reload_listener(*, on_reload: Callable[[dict], None] | None = None) -> None:
    """启动后台线程监听 reload 广播（幂等）。"""
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive():
        return
    _stop_event.clear()

    def _runner() -> None:
        _listen_loop(on_reload)

    _listener_thread = threading.Thread(target=_runner, name="workflow-reload-listener", daemon=True)
    _listener_thread.start()


def stop_reload_listener() -> None:
    """停止 reload 监听线程。"""
    global _listener_thread
    _stop_event.set()
    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=3)
    _listener_thread = None
