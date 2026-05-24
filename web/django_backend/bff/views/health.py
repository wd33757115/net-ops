import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..proxy_client import HEALTH_TIMEOUT, proxy_to_fastapi

logger = logging.getLogger("bff.views.health")


@csrf_exempt
async def proxy_health(request: HttpRequest) -> JsonResponse:
    return await proxy_to_fastapi(
        method="GET",
        fastapi_path="/health",
        request_id=request.bff_request_id,
        timeout=HEALTH_TIMEOUT,
    )
