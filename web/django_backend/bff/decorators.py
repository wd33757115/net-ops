import asyncio
from functools import wraps

from asgiref.sync import async_to_sync
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .response import bff_error


def _auth_required() -> bool:
    return getattr(settings, "BFF_REQUIRE_AUTH", not settings.DEBUG)


def _format_auth_error(detail) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def _authenticate_request(request):
    jwt_auth = JWTAuthentication()
    try:
        return jwt_auth.authenticate(request)
    except AuthenticationFailed as exc:
        return bff_error(_format_auth_error(exc.detail), 401)


def require_jwt(view_func):
    """BFF JWT 鉴权：兼容同步/异步视图。"""

    if asyncio.iscoroutinefunction(view_func):

        @wraps(view_func)
        async def async_wrapper(request, *args, **kwargs):
            if not _auth_required():
                return await view_func(request, *args, **kwargs)
            auth_result = _authenticate_request(request)
            if not isinstance(auth_result, tuple):
                return auth_result
            request.user, request.auth = auth_result
            return await view_func(request, *args, **kwargs)

        return async_wrapper

    @wraps(view_func)
    def sync_wrapper(request, *args, **kwargs):
        if not _auth_required():
            return view_func(request, *args, **kwargs)
        auth_result = _authenticate_request(request)
        if not isinstance(auth_result, tuple):
            return auth_result
        request.user, request.auth = auth_result
        return view_func(request, *args, **kwargs)

    return sync_wrapper
