# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..sync_async import sync_bff_view
from ..proxy_client import DEFAULT_TIMEOUT, proxy_to_fastapi
from ._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.itsm")


@csrf_exempt
@sync_bff_view
async def proxy_itsm_webhook(request: HttpRequest) -> JsonResponse:
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/itsm/webhook",
        request_id=request.bff_request_id,
        data=data,
        timeout=DEFAULT_TIMEOUT,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@sync_bff_view
async def proxy_firewall_policy_webhook(request: HttpRequest) -> JsonResponse:
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/itsm/webhook/firewall-policy",
        request_id=request.bff_request_id,
        data=data,
        timeout=DEFAULT_TIMEOUT,
        extra_headers=forward_client_headers(request),
    )


@csrf_exempt
@sync_bff_view
async def proxy_itsm_callback(request: HttpRequest) -> JsonResponse:
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/itsm/webhook/callback",
        request_id=request.bff_request_id,
        data=data,
        timeout=DEFAULT_TIMEOUT,
        extra_headers=forward_client_headers(request),
    )
