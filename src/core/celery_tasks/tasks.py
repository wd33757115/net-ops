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


def _legacy_skill_execute(skill_name: str, **params: Any) -> dict[str, Any]:
    """兼容旧 Celery 任务：委托通用 Skill 执行器。"""
    from src.core.skills.executor import SkillExecutionError, execute_skill

    try:
        return execute_skill(skill_name, params)
    except SkillExecutionError as exc:
        return {"success": False, "message": str(exc), "error": str(exc)}


@celery.task(bind=True, max_retries=0)
def execute_firewall_policy_task(self, **kwargs):
    """[兼容] 委托 firewall-policy-generator；Workflow 新路径请用 execute_skill_task。"""
    return _legacy_skill_execute("firewall-policy-generator", **kwargs)


@celery.task(bind=True, max_retries=1)
def execute_itsm_change_ticket_task(self, **kwargs):
    """[兼容] 委托 itsm-change-ticket-writer；Workflow 新路径请用 execute_skill_task。"""
    return _legacy_skill_execute("itsm-change-ticket-writer", **kwargs)


@celery.task(bind=True, max_retries=3, retry_backoff=5)
def execute_itsm_callback_task(self, **kwargs):
    """[兼容] 委托 itsm-callback；Workflow 新路径请用 execute_skill_task。"""
    return _legacy_skill_execute("itsm-callback", **kwargs)


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
