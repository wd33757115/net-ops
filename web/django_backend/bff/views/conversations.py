import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..proxy_client import DEFAULT_TIMEOUT, proxy_to_fastapi

logger = logging.getLogger("bff.views.conversations")


@csrf_exempt
async def proxy_conversations(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        params = {}
        if request.GET.get("user_id"):
            params["user_id"] = request.GET.get("user_id")
        if request.GET.get("limit"):
            params["limit"] = request.GET.get("limit")
        if request.GET.get("offset"):
            params["offset"] = request.GET.get("offset")
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path="/api/v1/conversations",
            request_id=request.bff_request_id,
            params=params,
        )
    else:
        data = _parse_body(request)
        return await proxy_to_fastapi(
            method="POST",
            fastapi_path="/api/v1/conversations",
            request_id=request.bff_request_id,
            data=data,
        )


@csrf_exempt
async def proxy_conversation_detail(request: HttpRequest, conversation_id: str) -> JsonResponse:
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path=f"/api/v1/conversations/{conversation_id}",
            request_id=request.bff_request_id,
        )
    elif request.method == "PUT":
        data = _parse_body(request)
        return await proxy_to_fastapi(
            method="PUT",
            fastapi_path=f"/api/v1/conversations/{conversation_id}",
            request_id=request.bff_request_id,
            data=data,
        )
    else:
        return await proxy_to_fastapi(
            method="DELETE",
            fastapi_path=f"/api/v1/conversations/{conversation_id}",
            request_id=request.bff_request_id,
        )


@csrf_exempt
async def proxy_add_message(request: HttpRequest, conversation_id: str) -> JsonResponse:
    data = _parse_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path=f"/api/v1/conversations/{conversation_id}/messages",
        request_id=request.bff_request_id,
        data=data,
    )


@csrf_exempt
async def proxy_summarize_conversation(request: HttpRequest, conversation_id: str) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path=f"/api/v1/conversations/{conversation_id}/summarize",
        request_id=request.bff_request_id,
    )


def _parse_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
