import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..proxy_client import CHAT_TIMEOUT, proxy_to_fastapi

logger = logging.getLogger("bff.views.chat")


@csrf_exempt
async def proxy_chat(request: HttpRequest) -> JsonResponse:
    data = _parse_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/chat",
        request_id=request.bff_request_id,
        data=data,
        timeout=CHAT_TIMEOUT,
    )


@csrf_exempt
async def proxy_chat_upload(request: HttpRequest) -> JsonResponse:
    data = _parse_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/chat/upload",
        request_id=request.bff_request_id,
        data=data,
        timeout=CHAT_TIMEOUT,
    )


def _parse_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
