"""FastAPI 认证依赖。"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from src.auth.models import CurrentUser
from src.auth.rbac import require_roles
from src.auth.security import resolve_current_user
from src.gateway.bff_security import is_enforce_bff_origin_enabled


async def get_optional_user(request: Request) -> CurrentUser | None:
    return resolve_current_user(request.headers)


async def get_current_user(request: Request) -> CurrentUser:
    user = resolve_current_user(request.headers)
    if user:
        return user
    if is_enforce_bff_origin_enabled():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或 BFF 未注入用户上下文",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录，请先通过 Django BFF 登录",
    )


def require_role(allowed_roles: list[str]):
    """工厂：限制角色访问。"""

    async def _dependency(request: Request) -> CurrentUser:
        user = await get_current_user(request)
        if not require_roles(user.role, allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色 {user.role} 无权访问此资源",
            )
        return user

    return _dependency
