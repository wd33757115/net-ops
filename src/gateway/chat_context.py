"""聊天上下文准备（REST / SSE 共用）。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from langchain_core.messages import HumanMessage

from src.auth.models import CurrentUser
from src.gateway.conversation_service import get_conversation_service
from src.gateway.schemas import ChatRequest


@dataclass
class PreparedChat:
    conversation_id: str
    graph_thread_id: str
    effective_user_id: str | None
    initial_state: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)
    callbacks: list[Any] = field(default_factory=list)


def validate_chat_user(user: CurrentUser | None, *, enforce_auth: bool) -> None:
    if enforce_auth and not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    if user and not user.can_execute_skills():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前角色仅可浏览，无法执行运维 Skill",
        )


def prepare_chat(
    request: ChatRequest,
    user: CurrentUser | None,
    *,
    callbacks: list[Any] | None = None,
) -> PreparedChat:
    """解析会话、thread_id、initial_state 与 LangGraph config。"""
    effective_user_id = user.user_id if user else request.user_id
    conv_service = get_conversation_service()
    conversation_id = request.thread_id

    if not conversation_id:
        conversation = conv_service.create_conversation(title="新对话", user_id=effective_user_id)
        conversation_id = conversation["id"]
    else:
        if effective_user_id:
            conversation = conv_service.get_conversation_for_user(conversation_id, effective_user_id)
        else:
            conversation = conv_service.get_conversation(conversation_id)
        if not conversation:
            conversation = conv_service.create_conversation(title="新对话", user_id=effective_user_id)
            conversation_id = conversation["id"]

    graph_thread_id = f"thread-{conversation_id.split('-')[-1]}"
    if user and user.thread_prefix:
        graph_thread_id = f"{user.thread_prefix}-{conversation_id.split('-')[-1]}"

    conv_service.update_conversation(
        conversation_id,
        thread_id=graph_thread_id,
        user_id=effective_user_id,
    )

    initial_state: dict[str, Any] = {
        "messages": [HumanMessage(content=request.query)],
        "source": request.source.value,
        "task_id": str(uuid.uuid4()),
        "thread_id": graph_thread_id,
    }
    if user:
        initial_state["user_id"] = user.user_id
        initial_state["user_role"] = user.role

    if request.metadata_filters:
        initial_state["metadata_filters"] = request.metadata_filters
    if request.uploaded_file_path:
        initial_state["uploaded_file_path"] = request.uploaded_file_path
    if request.ticket_id:
        initial_state["ticket_id"] = request.ticket_id

    config: dict[str, Any] = {
        "configurable": {"thread_id": graph_thread_id},
    }
    if callbacks:
        config["callbacks"] = callbacks

    return PreparedChat(
        conversation_id=conversation_id,
        graph_thread_id=graph_thread_id,
        effective_user_id=effective_user_id,
        initial_state=initial_state,
        config=config,
        callbacks=callbacks or [],
    )
