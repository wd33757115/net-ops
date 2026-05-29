import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from typing import Any

from src.core.celery_tasks.celery_app import celery

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, BASE_DIR)


from src.common.config import get_settings
from src.infrastructure.storage.minio_client import get_minio_storage

settings = get_settings()


@celery.task(bind=True, max_retries=0)
def execute_firewall_policy_task(
    self,
    ticket_id: str,
    ticket_title: str = "防火墙策略生成",
    policy_file_url: str | None = None,
    topology_file_url: str | None = None,
    parameters: dict | None = None,
    requester: str = "",
    assignee: str = "",
    change_background: str = "",
    change_purpose: str = "",
    requester_dept: str = "",
    priority: str = "P2",
    due_date: str | None = None,
    workflow_run_id: str | None = None,
    **kwargs,
):
    """执行防火墙策略生成（产物含 manifest + file_key；ITSM 回调由 Workflow 第 3 步负责）。"""
    import requests

    from src.core.firewall_policy.manifest import build_manifest_from_output, write_manifest_file
    from src.core.workflows.artifacts import make_file_artifact

    task_id = self.request.id
    execution_start = datetime.now()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir, exist_ok=True)

            policy_filename = f"policy_{ticket_id or 'draft'}.xlsx"
            policy_path = os.path.join(tmpdir, policy_filename)

            if not policy_file_url:
                from src.core.firewall_policy.paths import DEFAULT_POLICY_FILE

                default_policy = str(DEFAULT_POLICY_FILE)
                if os.path.exists(default_policy):
                    shutil.copy(default_policy, policy_path)
                else:
                    raise Exception("未提供策略文件且默认测试文件不存在")
            elif policy_file_url.startswith(("http://", "https://")):
                response = requests.get(policy_file_url, timeout=60)
                response.raise_for_status()
                with open(policy_path, "wb") as f:
                    f.write(response.content)
            elif policy_file_url.startswith("file://"):
                actual_path = policy_file_url[7:]
                if os.path.exists(actual_path):
                    shutil.copy(actual_path, policy_path)
                else:
                    raise Exception(f"策略文件不存在: {actual_path}")
            elif os.path.exists(policy_file_url):
                shutil.copy(policy_file_url, policy_path)
            else:
                raise Exception(f"策略文件不存在: {policy_file_url}")

            from src.core.firewall_policy.paths import (
                DEFAULT_TOPOLOGY_FILE,
                get_firewall_policy_cwd,
                get_firewall_policy_script,
            )

            topology_path = topology_file_url or str(DEFAULT_TOPOLOGY_FILE)
            if not os.path.exists(topology_path):
                topology_path = str(DEFAULT_TOPOLOGY_FILE)

            effective_ticket_id = (ticket_id or "").strip() or f"POLICY_{str(task_id)[:8]}"

            import subprocess

            script_path = get_firewall_policy_script()
            cmd = [
                sys.executable,
                str(script_path),
                "-t",
                topology_path,
                "-p",
                policy_path,
                "-o",
                output_dir,
                "-u",
                requester or "system",
                "--ticket-id",
                effective_ticket_id,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(get_firewall_policy_cwd()),
            )
            if result.returncode != 0:
                raise Exception(f"策略生成失败: {result.stderr}")

            manifest = build_manifest_from_output(
                output_dir,
                ticket_id=effective_ticket_id,
                ticket_title=ticket_title,
                change_background=change_background or ticket_title,
                change_purpose=change_purpose or "开通防火墙策略",
                requester=requester,
                requester_dept=requester_dept,
                priority=priority,
                due_date=due_date,
                topology_path=topology_path,
                trace_id=workflow_run_id,
            )
            write_manifest_file(output_dir, manifest)

            zip_name = f"firewall_policies_{effective_ticket_id}.zip"
            zip_path = os.path.join(tmpdir, zip_name)
            shutil.make_archive(zip_path.replace(".zip", ""), "zip", output_dir)

            object_name = None
            download_url = None
            minio_client = get_minio_storage()
            if minio_client and minio_client.is_ready():
                object_name = f"firewall_policies/{effective_ticket_id}/{zip_name}"
                with open(zip_path, "rb") as f:
                    upload_success = minio_client.upload_file(
                        object_name, f, content_type="application/zip"
                    )
                if upload_success:
                    download_url = minio_client.get_presigned_url(object_name, expires=3600 * 24 * 7)

            execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)
            config_zip = make_file_artifact(
                file_key=object_name,
                download_url=download_url,
                filename=zip_name,
                content_type="application/zip",
            )
            return {
                "success": True,
                "status": "success",
                "message": "防火墙策略生成成功",
                "ticket_id": effective_ticket_id,
                "download_url": download_url,
                "config_file_key": object_name,
                "filename": zip_name,
                "manifest": manifest,
                "artifacts": {
                    "config_zip": config_zip,
                    "manifest": manifest,
                },
                "execution_time_ms": execution_time_ms,
            }

    except Exception as e:
        raise e


@celery.task(bind=True, max_retries=1)
def execute_itsm_change_ticket_task(
    self,
    ticket_id: str,
    ticket_title: str = "",
    change_background: str = "",
    change_purpose: str = "",
    requester: str = "",
    requester_dept: str = "",
    priority: str = "P2",
    due_date: str | None = None,
    config_file_key: str | None = None,
    config_files_url: str | None = None,
    manifest: dict | None = None,
    workflow_run_id: str | None = None,
    **kwargs,
):
    """根据防火墙策略产物生成变更工单 Excel。"""
    from datetime import datetime

    from src.core.itsm.change_ticket_excel import build_change_ticket_workbook
    from src.core.itsm.zip_manifest_parser import load_manifest
    from src.core.workflows.artifacts import make_file_artifact

    execution_start = datetime.now()
    try:
        m = load_manifest(manifest=manifest, file_key=config_file_key, zip_url=config_files_url)
        m.setdefault("ticket_id", ticket_id)
        m.setdefault("ticket_title", ticket_title)
        if change_background:
            m["change_background"] = change_background
        if change_purpose:
            m["change_purpose"] = change_purpose

        excel_bytes = build_change_ticket_workbook(
            m,
            config_zip_url=config_files_url,
            workflow_run_id=workflow_run_id,
        )
        excel_name = f"变更工单_{ticket_id}_{execution_start.strftime('%Y%m%d%H%M%S')}.xlsx"
        object_name = None
        download_url = None
        minio = get_minio_storage()
        if minio and minio.is_ready():
            object_name = f"change_tickets/{ticket_id}/{excel_name}"
            if minio.upload_file(
                object_name,
                excel_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ):
                download_url = minio.get_presigned_url(object_name, expires=3600 * 24 * 7)

        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)
        change_excel = make_file_artifact(
            file_key=object_name,
            download_url=download_url,
            filename=excel_name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        return {
            "success": True,
            "message": "变更工单 Excel 已生成",
            "change_excel_url": download_url,
            "change_excel_file_key": object_name,
            "change_excel_filename": excel_name,
            "download_url": download_url,
            "artifacts": {"change_excel": change_excel},
            "execution_time_ms": execution_time_ms,
        }
    except Exception as exc:
        return {"success": False, "message": str(exc), "error": str(exc)}


@celery.task(bind=True, max_retries=3, retry_backoff=5)
def execute_itsm_callback_task(
    self,
    ticket_id: str,
    callback_url: str | None = None,
    callback_headers: dict | None = None,
    change_excel_url: str | None = None,
    change_excel_file_key: str | None = None,
    config_files_url: str | None = None,
    config_file_key: str | None = None,
    workflow_run_id: str | None = None,
    **kwargs,
):
    """回调 ITSM，附带 ZIP 与变更工单 Excel。"""
    from datetime import datetime

    from src.core.itsm.callback_client import build_callback_payload, post_itsm_callback
    from src.core.workflows.artifacts import make_file_artifact

    execution_start = datetime.now()
    if not callback_url:
        return {
            "success": True,
            "message": "未配置 callback_url，跳过 ITSM 回调",
            "callback_status": "skipped",
        }

    minio = get_minio_storage()
    zip_url = config_files_url
    if not zip_url and config_file_key and minio and minio.is_ready():
        zip_url = minio.get_presigned_url(config_file_key, expires=3600 * 24 * 7)
    excel_url = change_excel_url
    if not excel_url and change_excel_file_key and minio and minio.is_ready():
        excel_url = minio.get_presigned_url(change_excel_file_key, expires=3600 * 24 * 7)

    config_zip = make_file_artifact(
        file_key=config_file_key,
        download_url=zip_url,
        filename=f"firewall_policies_{ticket_id}.zip",
    )
    change_excel = make_file_artifact(
        file_key=change_excel_file_key,
        download_url=excel_url,
        filename=f"变更工单_{ticket_id}.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)
    payload = build_callback_payload(
        ticket_id=ticket_id,
        status="success",
        config_zip=config_zip,
        change_excel=change_excel,
        execution_time_ms=execution_time_ms,
        workflow_run_id=workflow_run_id,
    )
    ok, status_code, body = post_itsm_callback(callback_url, payload, callback_headers)
    return {
        "success": ok,
        "message": "ITSM 回调成功" if ok else f"ITSM 回调失败: HTTP {status_code}",
        "callback_status": "success" if ok else "failed",
        "http_status": status_code,
        "response_body": body,
        "artifacts": {"config_zip": config_zip, "change_excel": change_excel},
        "execution_time_ms": execution_time_ms,
        "error": None if ok else body,
    }


@celery.task(bind=True, max_retries=3, retry_backoff=2)
def execute_config_backup_task(
    self,
    filter_params: dict[str, Any],
    ticket_id: str | None = None,
    **kwargs
):
    """执行配置备份任务"""
    task_id = self.request.id
    execution_start = datetime.now()

    print(f"[DEBUG] config_backup task - task_id: {task_id}")
    print(f"[DEBUG] config_backup task - filter_params: {filter_params}")
    print(f"[DEBUG] config_backup task - ticket_id: {ticket_id}")

    try:
        from src.core.device_ops.loader import import_netops_agent_tools

        netops = import_netops_agent_tools()
        ConfigBackupTool = netops.ConfigBackupTool
        DBManager = netops.DBManager
        DeviceFilter = netops.DeviceFilter

        db_manager = DBManager()
        backup_tool = ConfigBackupTool(db_manager)

        device_filter = DeviceFilter(**filter_params) if filter_params else DeviceFilter()

        import asyncio
        result = asyncio.run(backup_tool.backup_by_filter(device_filter))

        minio_client = get_minio_storage()
        download_url = None
        output_files = result.output_files or []

        if minio_client and minio_client.is_ready() and output_files:
            print("[DEBUG] MinIO is ready, uploading config backup files...")

            if not ticket_id:
                ticket_id = f"BACKUP_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, f"config_backup_{ticket_id}.zip")
                output_dir = os.path.dirname(output_files[0]) if output_files else tmpdir
                shutil.make_archive(zip_path.replace(".zip", ""), "zip", output_dir)

                object_name = f"config_backup/{ticket_id}/{os.path.basename(zip_path)}"
                print(f"[DEBUG] Uploading config backup to MinIO: {object_name}")

                with open(zip_path, "rb") as f:
                    upload_success = minio_client.upload_file(object_name, f)

                if upload_success:
                    download_url = minio_client.get_presigned_url(object_name, expires=3600*24*7)
                    print(f"[DEBUG] Config backup download URL: {download_url}")

        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)

        return {
            "status": "success",
            "action": "backup",
            "ticket_id": ticket_id,
            "download_url": download_url,
            "total_devices": result.total_devices,
            "success_devices": result.success_devices,
            "failed_devices": result.failed_devices,
            "output_files": result.output_files,
            "execution_time_ms": execution_time_ms,
            "message": result.message
        }

    except Exception as e:
        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)
        print(f"[DEBUG] config_backup task failed: {str(e)}")
        # max_retries=0 时直接抛出异常，不重试
        raise e


@celery.task(bind=True, max_retries=3, retry_backoff=2)
def execute_device_patrol_task(
    self,
    filter_params: dict[str, Any],
    ticket_id: str | None = None,
    save_baseline: bool = False,
    **kwargs
):
    """执行设备巡检任务"""
    task_id = self.request.id
    execution_start = datetime.now()

    print(f"[DEBUG] device_patrol task - task_id: {task_id}")
    print(f"[DEBUG] device_patrol task - filter_params: {filter_params}")
    print(f"[DEBUG] device_patrol task - ticket_id: {ticket_id}")
    print(f"[DEBUG] device_patrol task - save_baseline: {save_baseline}")

    try:
        from src.core.device_ops.loader import import_netops_agent_tools

        netops = import_netops_agent_tools()
        DBManager = netops.DBManager
        DeviceFilter = netops.DeviceFilter
        PatrolTool = netops.PatrolTool

        db_manager = DBManager()
        patrol_tool = PatrolTool(db_manager)

        device_filter = DeviceFilter(**filter_params) if filter_params else DeviceFilter()

        import asyncio
        result = asyncio.run(patrol_tool.patrol_by_filter(device_filter, save_baseline))

        minio_client = get_minio_storage()
        download_url = None
        output_files = result.output_files or []

        if minio_client and minio_client.is_ready() and output_files:
            print("[DEBUG] MinIO is ready, uploading patrol files...")

            if not ticket_id:
                ticket_id = f"PATROL_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, f"device_patrol_{ticket_id}.zip")
                output_dir = os.path.dirname(output_files[0]) if output_files else tmpdir
                shutil.make_archive(zip_path.replace(".zip", ""), "zip", output_dir)

                object_name = f"device_patrol/{ticket_id}/{os.path.basename(zip_path)}"
                print(f"[DEBUG] Uploading device patrol to MinIO: {object_name}")

                with open(zip_path, "rb") as f:
                    upload_success = minio_client.upload_file(object_name, f)

                if upload_success:
                    download_url = minio_client.get_presigned_url(object_name, expires=3600*24*7)
                    print(f"[DEBUG] Device patrol download URL: {download_url}")

        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)

        return {
            "status": "success",
            "action": "patrol",
            "ticket_id": ticket_id,
            "save_baseline": save_baseline,
            "download_url": download_url,
            "total_devices": result.total_devices,
            "success_devices": result.success_devices,
            "failed_devices": result.failed_devices,
            "output_files": result.output_files,
            "execution_time_ms": execution_time_ms,
            "message": result.message
        }

    except Exception as e:
        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)
        print(f"[DEBUG] device_patrol task failed: {str(e)}")
        # max_retries=0 时直接抛出异常，不重试
        raise e
