#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
net_config_backup.py
版本：v2（支持每个设备独立用户名和密码）
"""
from __future__ import annotations
import argparse
import logging
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
from device_manager import DBManager

try:
    import yaml
except ImportError:
    yaml = None
    logging.warning("YAML模块不可用，将使用JSON配置回退")
try:
    from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
except ImportError:
    raise ImportError("Netmiko模块未安装，请安装以支持设备连接")

# ----------------------- 常量 -----------------------
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "ssh_cmd.log"
MAX_LOG_SIZE = 10 * 1024 * 1024
OUTPUT_BASE_DIR = Path("outputs")
DEFAULT_CONFIG = Path("config.yaml")
LOG_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "ERROR": logging.ERROR}

def setup_logging(log_level: str) -> logging.Logger:
    if LOG_FILE.exists() and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        os.remove(LOG_FILE)
    level = LOG_LEVELS.get(log_level.upper(), logging.ERROR)
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()]
    )
    return logging.getLogger("ssh_cmd")

def load_config(path: Path, logger: logging.Logger) -> Dict[str, Any]:
    if not path.exists():
        logger.warning(f"配置文件未找到: {path}")
        return {}
    try:
        if path.suffix.lower() in (".yml", ".yaml") and yaml:
            return yaml.safe_load(path.read_text(encoding='utf-8'))
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}

def read_password(password_file: Path, logger: logging.Logger) -> str:
    if not password_file.exists():
        raise FileNotFoundError(f"密码文件未找到: {password_file}")
    content = password_file.read_text(encoding='utf-8').strip()
    parts = [p.strip() for p in content.split(",")]
    return parts[-1]

def read_interactive_commands(logger: logging.Logger) -> List[str]:
    logger.info("进入交互模式，输入命令（每行一条），输入'end'结束：")
    cmds = []
    while True:
        line = sys.stdin.readline().strip()
        if line.lower() == "end":
            break
        if line:
            cmds.append(line)
    return cmds

class DeviceCommander:
    def __init__(self, config: Dict[str, Any], commands_dir: Path, run_timestamp: str, logger: logging.Logger):
        self.config = config
        self.commands_dir = commands_dir
        self.run_timestamp = run_timestamp
        self.logger = logger
        self.max_retries = 1
        self.retry_delay = float(self.config.get("retry_delay", 1.0))

    def _execute_command_with_retries(self, conn, cmd: str, device_id: str) -> Tuple[bool, str]:
        try:
            out = conn.send_command_timing(cmd, read_timeout=120)
            self.logger.info(f"设备 {device_id} 命令执行成功: {cmd}")
            return True, out
        except Exception as e:
            self.logger.error(f"设备 {device_id} 命令执行失败: {cmd} - {e}")
            return False, f"命令执行失败: {e}"

    def execute_device_commands(self, device: Dict[str, Any], output_dir: Optional[str] = None, interactive_cmds: Optional[List[str]] = None) -> Dict[str, Any]:
        start_time = time.time()
        device_name = device.get("device_name", "unknown")
        ip = device.get("ip", "unknown")
        device_id = f"{device_name}-{ip}"
        out_path = output_dir or device.get("out_path")
        command_file = device.get("command_file")
        device_type = self.config.get("default_device_type", "generic_ssh")

        results = {"device_id": device_id, "commands_executed": 0, "success": 0, "failed": 0}

        if not out_path:
            self.logger.error(f"设备 {device_id} 未指定输出路径，跳过")
            return results

        out_dir = OUTPUT_BASE_DIR / self.run_timestamp / out_path
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{device_id}.txt"

        cmds: List[str] = interactive_cmds or []
        if not cmds and command_file:
            cmd_path = self.commands_dir / command_file
            if cmd_path.exists():
                cmds = [l.strip() for l in cmd_path.read_text(encoding='utf-8').splitlines() if l.strip()]
            else:
                self.logger.error(f"命令文件未找到: {cmd_path}")
                return results
        if not cmds:
            self.logger.error(f"设备 {device_id} 没有命令，跳过")
            return results

        results["commands_executed"] = len(cmds)

        # ==================== 支持每个设备独立凭证 ====================
        device_username = device.get("username") or self.config.get("default_username", "admin")
        device_password = device.get("password") or self.config.get("_password")

        if not device_password:
            self.logger.error(f"设备 {device_id} 缺少密码！")
            results["failed"] = len(cmds)
            return results
        # ============================================================

        conn = None
        try:
            conn = ConnectHandler(
                device_type=device_type,
                ip=ip,
                username=device_username,
                password=device_password,
                read_timeout_override=60,
                global_delay_factor=1
            )
            self.logger.info(f"设备 {device_id} 连接成功")
            conn.clear_buffer(backoff=True)
        except Exception as e:
            self.logger.error(f"设备 {device_id} 连接失败: {e}")
            results["failed"] = len(cmds)
            return results

        outputs = []
        for cmd in cmds:
            success, output = self._execute_command_with_retries(conn, cmd, device_id)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
            outputs.append(f"命令: {cmd}\n输出:\n{output}\n{'-'*50}")

        try:
            with output_file.open("w", encoding='utf-8') as f:
                f.write("\n".join(outputs))
            self.logger.info(f"输出已保存: {output_file}")
        except Exception as e:
            self.logger.error(f"保存失败: {e}")

        conn.disconnect()
        self.logger.info(f"设备 {device_id} 处理完成，耗时 {time.time()-start_time:.2f}s")
        return results

def main() -> None:
    start_time = time.time()
    beijing_tz = timezone(timedelta(hours=8))
    run_timestamp = datetime.now(beijing_tz).strftime("%Y%m%d%H%M%S")

    parser = argparse.ArgumentParser(description="网络设备SSH命令执行工具 v2")
    parser.add_argument("--password", "-pwd", required=False, help="全局密码文件（设备没存密码时使用）")
    parser.add_argument("--config", "-c", default=str(DEFAULT_CONFIG))
    parser.add_argument("--workers", "-w", type=int, default=10)
    parser.add_argument("--log-level", "-l", default="DEBUG", choices=["DEBUG", "INFO", "ERROR"])
    parser.add_argument("--group", help="执行指定分组")
    parser.add_argument("--output-dir", help="指定输出目录")
    parser.add_argument("--devices", "-p", help="兼容旧Excel")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.log_level)
    config = load_config(Path(args.config), logger)
    config.setdefault("default_username", "admin")
    config.setdefault("default_device_type", "generic_ssh")

    if args.password:
        config["_password"] = read_password(Path(args.password), logger)
    else:
        config["_password"] = None

    db = DBManager()

    if args.group:
        devices = db.get_devices_by_group(args.group)
        if not devices:
            logger.warning(f"分组 {args.group} 无设备")
            return
    else:
        if not args.devices:
            raise ValueError("必须指定 --group 或 --devices")
        devs_df = pd.read_excel(Path(args.devices))
        devices = devs_df.fillna("").to_dict(orient="records")

    interactive_cmds = read_interactive_commands(logger) if args.interactive else None

    commands_dir = Path(config.get("commands_path", "commands"))
    commander = DeviceCommander(config, commands_dir, run_timestamp, logger)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(commander.execute_device_commands, d, args.output_dir, interactive_cmds): d for d in devices}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                logger.error(f"任务异常: {e}")

    logger.info(f"全部执行完成，总耗时: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()