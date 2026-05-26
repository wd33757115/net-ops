import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

from .response import bff_error, bff_success


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
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return bff_error("Invalid JSON", 400)

    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        return bff_error("username and password are required", 400)

    user = authenticate(username=username, password=password)
    if user is None:
        return bff_error("Invalid credentials", 401)

    return bff_success(get_tokens_for_user(user))


@csrf_exempt
def bff_refresh(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return bff_error("Invalid JSON", 400)

    refresh_token = body.get("refresh")
    if not refresh_token:
        return bff_error("refresh token is required", 400)

    try:
        refresh = RefreshToken(refresh_token)
        return bff_success(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )
    except Exception:
        return bff_error("Invalid or expired refresh token", 401)
