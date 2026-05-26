import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt
from ..proxy_client import proxy_to_fastapi
from ..views._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.skills")


@csrf_exempt
@require_jwt
async def proxy_skills_list(request: HttpRequest) -> JsonResponse:
    headers = forward_client_headers(request)
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path="/api/v1/skills",
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/skills",
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
async def proxy_skills_stats(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path="/api/v1/skills/stats",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
async def proxy_reload_all_skills(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/skills/reload-all",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
async def proxy_skill_content(request: HttpRequest, skill_name: str) -> JsonResponse:
    headers = forward_client_headers(request)
    path = f"/api/v1/skills/{skill_name}/content"
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path=path,
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="PUT",
        fastapi_path=path,
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
async def proxy_skill_files(request: HttpRequest, skill_name: str) -> JsonResponse:
    headers = forward_client_headers(request)
    path = f"/api/v1/skills/{skill_name}/files"
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path=path,
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path=path,
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
async def proxy_skill_toggle(request: HttpRequest, skill_name: str) -> JsonResponse:
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="PATCH",
        fastapi_path=f"/api/v1/skills/{skill_name}/toggle",
        request_id=request.bff_request_id,
        data=data,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
async def proxy_skill_reload(request: HttpRequest, skill_name: str) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path=f"/api/v1/skills/{skill_name}/reload",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
async def proxy_skill_detail(request: HttpRequest, skill_name: str) -> JsonResponse:
    headers = forward_client_headers(request)
    path = f"/api/v1/skills/{skill_name}"
    if request.method == "PUT":
        data = parse_json_body(request)
        return await proxy_to_fastapi(
            method="PUT",
            fastapi_path=path,
            request_id=request.bff_request_id,
            data=data,
            extra_headers=headers,
        )
    return await proxy_to_fastapi(
        method="DELETE",
        fastapi_path=path,
        request_id=request.bff_request_id,
        extra_headers=headers,
    )
