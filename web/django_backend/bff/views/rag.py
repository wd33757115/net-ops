import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..proxy_client import DEFAULT_TIMEOUT, proxy_to_fastapi

logger = logging.getLogger("bff.views.rag")


@csrf_exempt
async def proxy_rag_search(request: HttpRequest) -> JsonResponse:
    data = _parse_body(request)
    return await proxy_to_fastapi(
        method="POST",
        fastapi_path="/api/v1/rag/search",
        request_id=request.bff_request_id,
        data=data,
    )


def _parse_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
