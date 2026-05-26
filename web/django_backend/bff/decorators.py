from functools import wraps

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .response import bff_error


def _auth_required() -> bool:
    return getattr(settings, "BFF_REQUIRE_AUTH", not settings.DEBUG)


def _format_auth_error(detail) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        return str(first)
    return str(detail)


def require_jwt(view_func):
    """异步 BFF 代理视图 JWT 鉴权装饰器。"""

    @wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        if not _auth_required():
            return await view_func(request, *args, **kwargs)

        jwt_auth = JWTAuthentication()
        try:
            auth_result = jwt_auth.authenticate(request)
        except AuthenticationFailed as exc:
            return bff_error(_format_auth_error(exc.detail), 401)

        if auth_result is None:
            return bff_error("Authentication required", 401)

        request.user, request.auth = auth_result
        return await view_func(request, *args, **kwargs)

    return wrapper
