"""Skill 执行结果持久化（PostgreSQL）。"""

from __future__ import annotations

import logging
from typing import Any

from src.core.skills.result import SkillExecutionResult
from src.infrastructure.db.postgres import get_db_session

logger = logging.getLogger(__name__)


def save_skill_execution(result: SkillExecutionResult) -> bool:
    """写入 netops_skill_executions；失败时记录日志但不抛异常。"""
    try:
        from src.infrastructure.db.models import SkillExecutionRecord

        record = SkillExecutionRecord(
            execution_id=result.execution_id,
            skill_name=result.skill_name,
            skill_version=result.skill_version,
            status=result.status.value,
            message=result.message,
            input_params=result.metadata.get("input_params"),
            output=result.output or None,
            artifacts={k: v.model_dump() for k, v in result.artifacts.items()} or None,
            exec_metadata=result.metadata or None,
            error_info=result.error_info.model_dump() if result.error_info else None,
            context=result.context.model_dump(),
            thread_id=result.context.thread_id,
            message_id=result.context.message_id,
            user_id=result.context.user_id,
            ticket_id=result.context.ticket_id,
            source=result.context.source,
            executed_at=result.executed_at,
        )
        with get_db_session() as session:
            session.merge(record)
        return True
    except Exception as exc:
        logger.warning("保存 Skill 执行记录失败 execution_id=%s: %s", result.execution_id, exc)
        return False


def get_skill_execution(execution_id: str) -> dict[str, Any] | None:
    """按 execution_id 读取执行记录摘要。"""
    try:
        from src.infrastructure.db.models import SkillExecutionRecord

        with get_db_session() as session:
            row = session.get(SkillExecutionRecord, execution_id)
            if not row:
                return None
            return {
                "execution_id": row.execution_id,
                "skill_name": row.skill_name,
                "status": row.status,
                "message": row.message,
                "output": row.output,
                "artifacts": row.artifacts,
                "context": row.context,
                "executed_at": row.executed_at.isoformat() if row.executed_at else None,
            }
    except Exception as exc:
        logger.warning("读取 Skill 执行记录失败 execution_id=%s: %s", execution_id, exc)
        return None
