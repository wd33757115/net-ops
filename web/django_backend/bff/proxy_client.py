import logging
from typing import Any

import httpx
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse

logger = logging.getLogger("bff.proxy")

FASTAPI_BASE_URL = getattr(settings, "FASTAPI_BASE_URL", "http://localhost:8000")

_client: httpx.AsyncClient | None = None
_client_ws: httpx.AsyncClient | None = None  # WebSocket 专用客户端

DEFAULT_TIMEOUT = 30
CHAT_TIMEOUT = 180
HEALTH_TIMEOUT = 5
TASK_TIMEOUT = 30


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _client


def _get_ws_client() -> httpx.AsyncClient:
    global _client_ws
    if _client_ws is None or _client_ws.is_closed:
        _client_ws = httpx.AsyncClient(
            timeout=httpx.Timeout(CHAT_TIMEOUT),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
    return _client_ws


def _build_url(path: str) -> str:
    return f"{FASTAPI_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _build_headers(request_id: str, extra: dict | None = None) -> dict:
    headers = {
        "X-Request-ID": request_id,
        "X-Forwarded-From": "django-bff",
    }
    if extra:
        headers.update(extra)
    return headers


async def _proxy_json_response(
    response: httpx.Response,
    request_id: str,
) -> JsonResponse:
    if response.status_code == 204:
        return JsonResponse({}, status=204)

    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}

    wrapped = {
        "data": body,
        "meta": {"request_id": request_id, "upstream_status": response.status_code},
    }
    return JsonResponse(wrapped, status=response.status_code, safe=False)


async def proxy_request(
    method: str,
    path: str,
    request_id: str,
    data: dict | None = None,
    params: dict | None = None,
    timeout: int | None = None,
    extra_headers: dict | None = None,
    json_response: bool = True,
) -> JsonResponse:
    client = _get_client()
    url = _build_url(path)
    headers = _build_headers(request_id, extra_headers)

    req_kwargs: dict[str, Any] = {"headers": headers}
    if timeout is not None:
        req_kwargs["timeout"] = httpx.Timeout(timeout)
    if params:
        req_kwargs["params"] = params
    if data is not None and method in ("POST", "PUT", "PATCH"):
        req_kwargs["json"] = data

    try:
        response = await client.request(method, url, **req_kwargs)
        if json_response:
            return await _proxy_json_response(response, request_id)
        return JsonResponse({"raw": response.text}, status=response.status_code)
    except httpx.TimeoutException:
        logger.warning(f"[{request_id}] Upstream timeout: {method} {url}")
        return JsonResponse(
            {"error": f"Upstream service timeout after {timeout or DEFAULT_TIMEOUT}s"},
            status=504,
        )
    except httpx.ConnectError as e:
        logger.error(f"[{request_id}] Upstream connection failed: {method} {url} -> {e}")
        return JsonResponse(
            {"error": f"Upstream service unreachable: {str(e)}"},
            status=502,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Proxy error: {method} {url} -> {e}")
        return JsonResponse({"error": str(e)}, status=500)


async def proxy_to_fastapi(
    method: str,
    fastapi_path: str,
    request_id: str,
    data: dict | None = None,
    params: dict | None = None,
    timeout: int | None = None,
) -> JsonResponse:
    return await proxy_request(
        method=method,
        path=fastapi_path,
        request_id=request_id,
        data=data,
        params=params,
        timeout=timeout,
    )
