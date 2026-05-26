import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt
from ..proxy_client import CHAT_TIMEOUT, proxy_to_fastapi
from ._helpers import forward_client_headers, parse_json_body

logger = logging.getLogger("bff.views.upload")


@csrf_exempt
@require_jwt
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
