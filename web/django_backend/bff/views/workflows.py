import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt, require_role
from ..sync_async import sync_bff_view
from ..proxy_client import TASK_TIMEOUT, proxy_to_fastapi
from ._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.workflows")


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_templates(request: HttpRequest) -> JsonResponse:
    headers = forward_client_headers(request)
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path="/api/v1/workflows/templates",
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/templates",
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_template_detail(request: HttpRequest, name: str) -> JsonResponse:
    headers = forward_client_headers(request)
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path=f"/api/v1/workflows/templates/{name}",
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="PUT",
        fastapi_path=f"/api/v1/workflows/templates/{name}",
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_reload(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/reload",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_validate(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/validate",
        request_id=request.bff_request_id,
        data=parse_json_body(request),
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_collab_templates(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path="/api/v1/workflows/collab-templates",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_collab_template_generate(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/collab-templates/generate",
        request_id=request.bff_request_id,
        data=parse_json_body(request),
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_chat_intent_preview(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/chat-intent/preview",
        request_id=request.bff_request_id,
        data=parse_json_body(request),
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_runs(request: HttpRequest) -> JsonResponse:
    headers = forward_client_headers(request)
    params = dict(request.GET.items())
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path="/api/v1/workflows/runs",
        request_id=request.bff_request_id,
        params=params,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
@require_role("admin")
@sync_bff_view
async def proxy_workflow_test_run(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/workflows/runs/test",
        request_id=request.bff_request_id,
        timeout=TASK_TIMEOUT,
        data=parse_json_body(request),
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_workflow_detail(request: HttpRequest, run_id: str) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path=f"/api/v1/workflows/{run_id}",
        request_id=request.bff_request_id,
        timeout=TASK_TIMEOUT,
        extra_headers=forward_client_headers(request),
    )
