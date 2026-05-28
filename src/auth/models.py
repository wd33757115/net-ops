"""认证与 RBAC 数据模型（Pydantic）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CurrentUser(BaseModel):
    """FastAPI 请求上下文中的当前用户。"""

    user_id: str
    username: str
    role: str = Field(default="operator", description="admin | operator | viewer")
    thread_prefix: str | None = None
    session_id: str | None = None

    def skill_permission_level(self) -> str:
        from src.auth.rbac import role_to_permission_level

        return role_to_permission_level(self.role)

    def can_execute_skills(self) -> bool:
        return self.role in {"admin", "operator"}

    def is_admin(self) -> bool:
        return self.role == "admin"
