"""Skill → Celery Queue 路由（基于 Catalog domain / celery_queue）。"""

from __future__ import annotations

from src.skill_system.catalog.repository import get_catalog_entry

DOMAIN_QUEUE_MAP: dict[str, str] = {
    "security": "netops.firewall",
    "network": "netops.device",
    "itsm": "netops.default",
    "general": "netops.default",
    "default": "netops.default",
}


def resolve_skill_celery_queue(skill_name: str) -> str:
    entry = get_catalog_entry(skill_name)
    if entry:
        if entry.get("celery_queue"):
            return str(entry["celery_queue"])
        domain = str(entry.get("domain") or "default").lower()
        return DOMAIN_QUEUE_MAP.get(domain, "netops.default")
    return DOMAIN_QUEUE_MAP["default"]
