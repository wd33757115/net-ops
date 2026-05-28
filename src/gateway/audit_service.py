"""审计日志写入 PostgreSQL。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.db.models import AuditLogRecord
from src.infrastructure.db.postgres import get_db_session


def write_audit_log(
    *,
    action: str,
    user_id: str | None = None,
    username: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
    status: str = "success",
) -> None:
    try:
        with get_db_session() as session:
            session.add(
                AuditLogRecord(
                    id=f"audit-{uuid.uuid4().hex[:16]}",
                    user_id=user_id,
                    username=username,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    ip_address=ip_address,
                    status=status,
                    created_at=datetime.now(timezone.utc),
                )
            )
    except Exception:
        # 审计失败不阻断主流程
        pass
