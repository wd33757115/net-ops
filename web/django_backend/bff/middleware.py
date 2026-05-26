import asyncio
import logging
import time
import uuid
from collections import defaultdict

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpRequest, JsonResponse

from .response import bff_error

logger = logging.getLogger("bff.middleware")


def _resolve_response(response):
    if asyncio.iscoroutine(response):
        async def _await_coro():
            return await response

        return async_to_sync(_await_coro)()
    return response


def _get_client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _attach_request_meta(request: HttpRequest) -> str:
    request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
    request.bff_request_id = request_id
    request.bff_start_time = time.monotonic()
    return request_id


def _log_request(request: HttpRequest, response, request_id: str) -> None:
    duration_ms = (time.monotonic() - request.bff_start_time) * 1000
    response["X-Request-ID"] = request_id
    logger.info(
        "bff_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": _get_client_ip(request),
        },
    )


class BFFRequestIDMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        request_id = _attach_request_meta(request)
        response = _resolve_response(self.get_response(request))
        _log_request(request, response, request_id)
        return response

    async def __acall__(self, request: HttpRequest):
        request_id = _attach_request_meta(request)
        response = await self.get_response(request)
        _log_request(request, response, request_id)
        return response


class BFFRateLimitMiddleware:
    """基于 IP 的简易限流中间件"""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._window: dict[str, list[float]] = defaultdict(list)
        self._limit_chat = 30
        self._limit_default = 60
        self._window_seconds = 60

    def _clean_window(self, ip: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        self._window[ip] = [t for t in self._window[ip] if t > cutoff]

    def _is_rate_limited(self, ip: str, path: str) -> bool:
        self._clean_window(ip)
        limit = self._limit_chat if "/chat/" in path else self._limit_default
        return len(self._window[ip]) >= limit

    def _check_rate_limit(self, request: HttpRequest):
        if settings.DEBUG:
            return None
        ip = _get_client_ip(request)
        if self._is_rate_limited(ip, request.path):
            return bff_error(
                "Rate limit exceeded. Please try again later.",
                429,
                data={"retry_after_seconds": self._window_seconds},
            )
        self._window[ip].append(time.monotonic())
        return None

    def __call__(self, request: HttpRequest):
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        limited = self._check_rate_limit(request)
        if limited is not None:
            return limited
        response = _resolve_response(self.get_response(request))
        return response

    async def __acall__(self, request: HttpRequest):
        limited = self._check_rate_limit(request)
        if limited is not None:
            return limited
        return await self.get_response(request)
