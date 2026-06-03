# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""下载链接签名与 URL 构建测试。"""

import time

from src.infrastructure.storage.download_urls import (
    build_object_download_url,
    compute_download_signature,
    verify_download_signature,
)


def test_build_object_download_url_relative():
    url = build_object_download_url("firewall_policies/T001/out.zip", filename="out.zip", expires=3600)
    assert url is not None
    assert url.startswith("/api/artifacts/download/?")
    assert "key=firewall_policies" in url
    assert "sig=" in url


def test_verify_download_signature_roundtrip():
    key = "skill_outputs/test/file.zip"
    exp = int(time.time()) + 3600
    sig = compute_download_signature(key, exp)
    assert verify_download_signature(key, exp, sig)
    assert not verify_download_signature(key, exp, "bad-signature")
    assert not verify_download_signature(key, exp - 7200, sig)


def test_build_object_download_url_with_public_base(monkeypatch):
    from src.common import config

    monkeypatch.setattr(config.settings, "PUBLIC_APP_URL", "https://netops.example.com")
    url = build_object_download_url("a/b.txt", expires=60)
    assert url.startswith("https://netops.example.com/api/artifacts/download/?")
