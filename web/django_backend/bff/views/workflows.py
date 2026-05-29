import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..decorators import require_jwt
from ..sync_async import sync_bff_view
from ..proxy_client import TASK_TIMEOUT, proxy_to_fastapi
from ._helpers import forward_client_headers

logger = logging.getLogger("bff.views.workflows")


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
