"""ZIP / manifest 解析。"""

from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from typing import Any

import requests

from src.infrastructure.storage.minio_client import get_minio_storage


def load_manifest(
    *,
    manifest: dict[str, Any] | None = None,
    file_key: str | None = None,
    zip_url: str | None = None,
) -> dict[str, Any]:
    if manifest:
        return manifest

    zip_bytes = _load_zip_bytes(file_key=file_key, zip_url=zip_url)
    if not zip_bytes:
        raise ValueError("无法加载策略 ZIP：缺少 manifest、file_key 或 zip_url")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        if "manifest.json" in zf.namelist():
            with zf.open("manifest.json") as mf:
                return json.loads(mf.read().decode("utf-8"))
        return _manifest_from_zip_entries(zf)


def _load_zip_bytes(*, file_key: str | None, zip_url: str | None) -> bytes | None:
    if file_key:
        data = get_minio_storage().download_file(file_key)
        if data:
            return data
    if zip_url:
        if zip_url.startswith(("http://", "https://")):
            resp = requests.get(zip_url, timeout=120)
            resp.raise_for_status()
            return resp.content
        if os.path.exists(zip_url):
            with open(zip_url, "rb") as f:
                return f.read()
    return None


def _manifest_from_zip_entries(zf: zipfile.ZipFile) -> dict[str, Any]:
    scripts = []
    order = 0
    for name in zf.namelist():
        if not name.lower().endswith((".txt", ".cfg", ".conf")):
            continue
        with zf.open(name) as f:
            content = f.read().decode("utf-8", errors="replace")
        device_name = os.path.splitext(os.path.basename(name))[0]
        order += 1
        lines = [ln for ln in content.splitlines() if ln.strip()]
        scripts.append(
            {
                "device_name": device_name,
                "vendor": "未知",
                "order": order,
                "commands": content,
                "command_count": len(lines),
            }
        )
    return {
        "ticket_id": "UNKNOWN",
        "devices": [{"device_name": s["device_name"], "vendor": s["vendor"]} for s in scripts],
        "scripts": scripts,
        "rollback": [],
    }
