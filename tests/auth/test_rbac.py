# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""认证与 RBAC 单元测试。"""

from unittest.mock import patch

import jwt

from src.auth.rbac import normalize_role, require_roles, role_to_permission_level
from src.auth.security import user_from_bff_headers, user_from_jwt_payload
from src.common.config import get_settings
from src.gateway.bff_security import is_trusted_bff_request


def test_role_mapping():
    assert role_to_permission_level("admin") == "admin"
    assert role_to_permission_level("operator") == "power_user"
    assert role_to_permission_level("viewer") == "guest"
    assert require_roles("admin", ["admin", "operator"]) is True
    assert require_roles("viewer", ["admin"]) is False


def test_bff_trusted_headers():
    headers = {
        "X-Forwarded-From": "django-bff",
        "X-Internal-Request": "true",
        "X-User-Id": "42",
        "X-User-Name": "admin",
        "X-User-Role": "admin",
        "X-User-Thread-Prefix": "user-42",
    }
    assert is_trusted_bff_request(headers) is True
    user = user_from_bff_headers(headers)
    assert user is not None
    assert user.user_id == "42"
    assert user.role == "admin"
    assert user.thread_prefix == "user-42"


def test_bff_headers_revoked_session():
    headers = {
        "X-Forwarded-From": "django-bff",
        "X-Internal-Request": "true",
        "X-User-Id": "42",
        "X-User-Name": "admin",
        "X-User-Role": "admin",
        "X-User-Thread-Prefix": "user-42",
        "X-Session-Id": "sess-revoked",
    }
    with patch("src.auth.security.is_auth_token_revoked", return_value=True):
        assert user_from_bff_headers(headers) is None


def test_jwt_payload_user():
    settings = get_settings()
    payload = {
        "user_id": 7,
        "username": "operator",
        "role": "operator",
        "thread_id": "user-7",
        "exp": 9999999999,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    user = user_from_jwt_payload(decoded)
    assert user.user_id == "7"
    assert user.username == "operator"
    assert normalize_role(user.role) == "operator"
