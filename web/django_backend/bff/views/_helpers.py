import json

from django.http import HttpRequest


def parse_json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def forward_client_headers(request: HttpRequest) -> dict:
    """将客户端可转发的请求头传递给 FastAPI。"""
    headers: dict[str, str] = {}
    if auth := request.META.get("HTTP_AUTHORIZATION"):
        headers["Authorization"] = auth
    if content_type := request.META.get("CONTENT_TYPE"):
        headers["Content-Type"] = content_type
    return headers
