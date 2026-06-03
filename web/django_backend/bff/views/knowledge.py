# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt
from ..sync_async import sync_bff_view
from ..proxy_client import proxy_to_fastapi
from ..views._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.knowledge")


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_knowledge_documents(request: HttpRequest) -> JsonResponse:
    headers = forward_client_headers(request)
    if request.method == "GET":
        return await proxy_to_fastapi(
            method="GET",
            fastapi_path="/api/v1/knowledge/documents",
            request_id=request.bff_request_id,
            extra_headers=headers,
        )
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/knowledge/documents",
        request_id=request.bff_request_id,
        data=data,
        extra_headers=headers,
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_knowledge_document_content(request: HttpRequest, doc_path: str) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path=f"/api/v1/knowledge/documents/{doc_path}/content",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_knowledge_document_detail(request: HttpRequest, doc_path: str) -> JsonResponse:
    auto_reindex = request.GET.get("auto_reindex", "true").lower() in ("1", "true", "yes")
    return await proxy_to_fastapi(
        method="DELETE",
        fastapi_path=f"/api/v1/knowledge/documents/{doc_path}?auto_reindex={str(auto_reindex).lower()}",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_knowledge_stats(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path="/api/v1/knowledge/stats",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_knowledge_reindex(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/knowledge/reindex",
        request_id=request.bff_request_id,
        extra_headers=forward_client_headers(request),
    )
