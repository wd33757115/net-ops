import logging
import time
import uuid
from collections import defaultdict

from django.http import HttpRequest, JsonResponse

logger = logging.getLogger("bff.middleware")


class BFFRequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.bff_request_id = request_id
        request.bff_start_time = time.monotonic()

        response = self.get_response(request)

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

        return response


class BFFRateLimitMiddleware:
    """基于 IP 的简易限流中间件"""

    def __init__(self, get_response):
        self.get_response = get_response
        self._window: dict[str, list[float]] = defaultdict(list)
        self._limit_chat = 30  # 聊天接口: 30 req/min
        self._limit_default = 60  # 其他接口: 60 req/min
        self._window_seconds = 60

    def _clean_window(self, ip: str):
        now = time.monotonic()
        cutoff = now - self._window_seconds
        self._window[ip] = [t for t in self._window[ip] if t > cutoff]

    def _is_rate_limited(self, ip: str, path: str) -> bool:
        self._clean_window(ip)
        limit = self._limit_chat if "/chat/" in path else self._limit_default
        return len(self._window[ip]) >= limit

    def __call__(self, request: HttpRequest):
        ip = _get_client_ip(request)
        if self._is_rate_limited(ip, request.path):
            return JsonResponse(
                {
                    "error": "Rate limit exceeded. Please try again later.",
                    "retry_after_seconds": self._window_seconds,
                },
                status=429,
            )

        now = time.monotonic()
        self._window[ip].append(now)
        return self.get_response(request)


def _get_client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
