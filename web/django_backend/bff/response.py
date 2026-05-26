from django.http import JsonResponse


def bff_success(data=None, status: int = 200) -> JsonResponse:
    payload = {"success": True, "data": data, "error": None}
    if status == 204:
        return JsonResponse(payload, status=200)
    return JsonResponse(payload, status=status, safe=False)


def bff_error(error: str, status: int = 400, data=None) -> JsonResponse:
    return JsonResponse(
        {"success": False, "data": data, "error": error},
        status=status,
        safe=False,
    )
