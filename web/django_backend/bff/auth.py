from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from ..proxy_client import proxy_to_fastapi


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }


@csrf_exempt
def bff_login(request):
    import json

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        return JsonResponse({"error": "username and password are required"}, status=400)

    user = authenticate(username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    tokens = get_tokens_for_user(user)
    return JsonResponse(tokens, status=200)


@csrf_exempt
def bff_refresh(request):
    import json

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    refresh_token = body.get("refresh")
    if not refresh_token:
        return JsonResponse({"error": "refresh token is required"}, status=400)

    try:
        refresh = RefreshToken(refresh_token)
        return JsonResponse(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=200,
        )
    except Exception:
        return JsonResponse({"error": "Invalid or expired refresh token"}, status=401)
