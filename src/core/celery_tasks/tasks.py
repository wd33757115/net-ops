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


@celery.task(bind=True, max_retries=0)   # max_retries=0: 失败不重试，快速失败让用户看到错误
def execute_firewall_policy_task(
    self,
    ticket_id: str,
    ticket_title: str,
    policy_file_url: str,
    topology_file_url: str | None = None,
    parameters: dict | None = None,
    callback_url: str | None = None,
    callback_headers: dict | None = None,
    requester: str = "",
    assignee: str = "",
    **kwargs
):
    """执行防火墙策略生成任务（失败不重试，快速失败）"""
    import requests

    task_id = self.request.id
    execution_start = datetime.now()

    print(f"[DEBUG] celery task - received ticket_id: {ticket_id}")
    print(f"[DEBUG] celery task - task_id: {task_id}")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir, exist_ok=True)

            policy_filename = f"policy_{ticket_id}.xlsx"
            policy_path = os.path.join(tmpdir, policy_filename)

            # 处理策略文件：支持 URL、file:// 路径、本地路径
            # 如果未提供 policy_file_url，使用默认测试文件
            if not policy_file_url:
                default_policy = os.path.join(BASE_DIR, "tools", "firewall-policy", "test_policy.xlsx")
                if os.path.exists(default_policy):
                    import shutil
                    shutil.copy(default_policy, policy_path)
                    print(f"[DEBUG] 使用默认策略文件: {default_policy}")
                else:
                    raise Exception(
                        "未提供策略文件(policy_file_url)，且默认测试文件不存在。"
                        "请上传策略Excel文件后重试。"
                    )
            elif policy_file_url.startswith(('http://', 'https://')):
                response = requests.get(policy_file_url, timeout=60)
                response.raise_for_status()
                with open(policy_path, "wb") as f:
                    f.write(response.content)
                print(f"[DEBUG] 已从URL下载策略文件: {policy_file_url}")
            elif policy_file_url.startswith('file://'):
                import shutil
                actual_path = policy_file_url[7:]
                if os.path.exists(actual_path):
                    shutil.copy(actual_path, policy_path)
                    print(f"[DEBUG] 已复制file://策略文件: {actual_path}")
                else:
                    raise Exception(f"策略文件不存在: {actual_path}")
            elif os.path.exists(policy_file_url):
                import shutil
                shutil.copy(policy_file_url, policy_path)
                print(f"[DEBUG] 已复制本地策略文件: {policy_file_url}")
            else:
                raise Exception(f"策略文件不存在: {policy_file_url}")

            topology_path = topology_file_url
            if not topology_path:
                topology_path = os.path.join(BASE_DIR, "tools", "firewall-policy", "topology.json")

            import subprocess
            cmd = [
                sys.executable,
                os.path.join(BASE_DIR, "tools", "firewall-policy", "firewall-policy.py"),
                "-t", topology_path,
                "-p", policy_path,
                "-o", output_dir,
                "-u", requester or "system",
                "-i", ticket_id
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                raise Exception(f"策略生成失败: {result.stderr}")

            output_files = []
            for root, dirs, files in os.walk(output_dir):
                for f in files:
                    output_files.append(os.path.join(root, f))

            minio_client = get_minio_storage()
            print(f"[DEBUG] MinIO client: {minio_client}")
            print(f"[DEBUG] MinIO client ready: {minio_client.is_ready() if minio_client else 'No client'}")

            if minio_client and minio_client.is_ready():
                print("[DEBUG] MinIO is ready, uploading file...")
                zip_path = os.path.join(tmpdir, f"firewall_policies_{ticket_id}.zip")
                shutil.make_archive(zip_path.replace(".zip", ""), "zip", output_dir)

                object_name = f"firewall_policies/{ticket_id}/{os.path.basename(zip_path)}"
                print(f"[DEBUG] Uploading to MinIO: {object_name}")
                with open(zip_path, "rb") as f:
                    upload_success = minio_client.upload_file(object_name, f)
                print(f"[DEBUG] Upload success: {upload_success}")

                if upload_success:
                    download_url = minio_client.get_presigned_url(object_name, expires=3600*24*7)
                    print(f"[DEBUG] Download URL: {download_url}")
                else:
                    download_url = None
            else:
                print("[DEBUG] MinIO not ready, setting download_url to None")
                download_url = None
                output_files = [f for f in output_files if os.path.isfile(f)]

            execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)

            if callback_url:
                callback_data = {
                    "version": "1.0",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                    "callback_id": f"cb_{uuid.uuid4().hex}",
                    "source_ticket_id": ticket_id,
                    "status": "success",
                    "result": {
                        "action": "update_ticket",
                        "ticket_update": {
                            "status": "配置已生成",
                            "resolution_note": "策略配置文件已生成，下载后请按照变更流程执行",
                            "attachments": []
                        }
                    },
                    "metadata": {
                        "execution_time_ms": execution_time_ms,
                        "task_id": task_id
                    }
                }

                if download_url:
                    callback_data["result"]["ticket_update"]["attachments"].append({
                        "filename": f"firewall_policies_{ticket_id}.zip",
                        "download_url": download_url
                    })

                headers = callback_headers or {}
                headers["Content-Type"] = "application/json"

                try:
                    requests.post(callback_url, json=callback_data, headers=headers, timeout=30)
                except Exception as e:
                    self.retry(exc=e, max_retries=self.max_retries)

            return {
                "status": "success",
                "action": "firewall",
                "ticket_id": ticket_id,
                "download_url": download_url,
                "output_files": output_files,
                "execution_time_ms": execution_time_ms
            }

    except Exception as e:
        execution_time_ms = int((datetime.now() - execution_start).total_seconds() * 1000)

        if callback_url:
            callback_data = {
                "version": "1.0",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "callback_id": f"cb_{uuid.uuid4().hex}",
                "source_ticket_id": ticket_id,
                "status": "failed",
                "error": {
                    "code": "POLICY_GEN_001",
                    "message": str(e),
                    "suggested_action": "请检查策略文件格式和网络连接"
                },
                "metadata": {
                    "execution_time_ms": execution_time_ms,
                    "retry_count": self.request.retries,
                    "failed_at_stage": "policy_generation"
                }
            }

            headers = callback_headers or {}
            headers["Content-Type"] = "application/json"
            try:
                requests.post(callback_url, json=callback_data, headers=headers, timeout=30)
            except requests.exceptions.RequestException:
                pass

        # max_retries=0 时直接抛出异常，不重试
        raise e


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
        from tools.netops_agent_tools import ConfigBackupTool, DBManager, DeviceFilter

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
        from tools.netops_agent_tools import DBManager, DeviceFilter, PatrolTool

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
