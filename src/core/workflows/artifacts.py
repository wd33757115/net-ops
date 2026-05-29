"""Skill / Celery 产物标准契约。"""

from __future__ import annotations

from typing import Any


def make_file_artifact(
    *,
    file_key: str | None,
    download_url: str | None,
    filename: str,
    content_type: str = "application/octet-stream",
) -> dict[str, Any]:
    return {
        "file_key": file_key,
        "download_url": download_url,
        "filename": filename,
        "content_type": content_type,
    }


def normalize_step_result(raw: dict[str, Any] | None) -> dict[str, Any]:
    """统一 Celery / Skill 返回结构。"""
    if not raw:
        return {"success": False, "message": "空结果", "artifacts": {}}
    success = bool(raw.get("success", raw.get("status") == "success"))
    artifacts = dict(raw.get("artifacts") or {})
    manifest = raw.get("manifest") or artifacts.get("manifest")
    if not artifacts.get("config_zip") and raw.get("download_url"):
        artifacts["config_zip"] = make_file_artifact(
            file_key=raw.get("config_file_key"),
            download_url=raw.get("download_url"),
            filename=raw.get("filename") or "firewall_policies.zip",
            content_type="application/zip",
        )
    if not artifacts.get("change_excel") and raw.get("change_excel_url"):
        artifacts["change_excel"] = make_file_artifact(
            file_key=raw.get("change_excel_file_key"),
            download_url=raw.get("change_excel_url"),
            filename=raw.get("change_excel_filename") or "change_ticket.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return {
        "success": success,
        "message": raw.get("message") or raw.get("result") or "",
        "artifacts": artifacts,
        "manifest": manifest,
        "download_url": raw.get("download_url"),
        "error": raw.get("error"),
    }


def merge_step_artifacts(*steps: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for step in steps:
        arts = (step or {}).get("artifacts") or {}
        merged.update(arts)
    return merged
