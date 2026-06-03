# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt
from ..sync_async import sync_bff_view
from ..proxy_client import CHAT_TIMEOUT, proxy_to_fastapi
from ._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.upload")


@csrf_exempt
@require_jwt
@sync_bff_view
async def proxy_chat_upload(request: HttpRequest) -> JsonResponse:
    data = parse_json_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/chat/upload",
        request_id=request.bff_request_id,
        data=data,
        timeout=CHAT_TIMEOUT,
        extra_headers=forward_client_headers(request),
    )
