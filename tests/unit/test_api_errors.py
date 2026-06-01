"""P2：统一 API 错误信封与异常处理器测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.common.exceptions import SkillNotFoundError
from src.core.exceptions import AppError, ErrorCode, error_envelope, normalize_error_detail
from src.gateway.exception_handlers import register_exception_handlers


@pytest.fixture
def api_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-404")
    def http_404():
        raise HTTPException(status_code=404, detail="Workflow 不存在")

    @app.get("/app-error")
    def app_error_route():
        raise AppError(
            "Skill 执行失败",
            code=ErrorCode.SKILL_EXECUTION_FAILED,
            status_code=400,
            details={"skill_name": "demo"},
        )

    @app.get("/domain-error")
    def domain_error_route():
        raise SkillNotFoundError("demo-skill")

    @app.get("/crash")
    def crash_route():
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_error_envelope_shape():
    body = error_envelope(
        code=ErrorCode.NOT_FOUND,
        message="未找到",
        request_id="req-1",
        details={"name": "x"},
    )
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["request_id"] == "req-1"


def test_normalize_validation_detail():
    message, details = normalize_error_detail(
        [{"loc": ["body", "name"], "msg": "field required", "type": "missing"}]
    )
    assert "field required" in message
    assert "errors" in details


def test_http_exception_returns_envelope(api_client: TestClient):
    response = api_client.get("/http-404", headers={"X-Request-Id": "trace-404"})
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Workflow 不存在"
    assert body["request_id"] == "trace-404"
    assert response.headers.get("X-Request-Id") == "trace-404"


def test_app_error_returns_envelope(api_client: TestClient):
    response = api_client.get("/app-error")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "skill_execution_failed"
    assert body["error"]["details"]["skill_name"] == "demo"


def test_netops_domain_error_mapping(api_client: TestClient):
    response = api_client.get("/domain-error")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "skill_not_found"


def test_unhandled_exception_returns_internal_error(api_client: TestClient):
    response = api_client.get("/crash")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "request_id" in body
