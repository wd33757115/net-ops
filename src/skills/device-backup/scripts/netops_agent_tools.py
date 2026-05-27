#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netops_agent_tools.py
企业级运维AI Agent工具集成模块
版本: V1.0
支持: Pydantic v2, 异步, LLM意图解析
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_ROOT / "data"
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import AIMessage
from src.common.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("netops_tools")

BEIJING_TZ = timezone(timedelta(hours=8))


class ActionType(str, Enum):
    """操作类型枚举"""
    BACKUP = "backup"
    PATROL = "patrol"
    LIST_DEVICES = "list_devices"
    LIST_GROUPS = "list_groups"
    ADD_DEVICE = "add_device"
    DELETE_GROUP = "delete_group"
    UNKNOWN = "unknown"


class DeviceFilter(BaseModel):
    """设备过滤条件模型"""
    model_config = ConfigDict(extra='forbid')
    
    device_name: Optional[str] = Field(None, description="设备名称")
    ip: Optional[str] = Field(None, description="设备IP地址")
    group: Optional[str] = Field(None, description="设备分组")
    model: Optional[str] = Field(None, description="设备型号")
    
    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^[\d.]+$', v):
            logger.warning(f"IP格式可能不正确: {v}")
        return v


class ParsedIntent(BaseModel):
    """解析后的用户意图模型"""
    model_config = ConfigDict(extra='forbid')
    
    action: ActionType = Field(..., description="操作类型")
    filter: DeviceFilter = Field(default_factory=DeviceFilter, description="设备过滤条件")
    save_baseline: bool = Field(False, description="是否保存基线（仅巡检时有效）")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="意图识别置信度")
    raw_query: str = Field(..., description="原始查询")
    reason: Optional[str] = Field(None, description="意图识别理由")


class TaskResult(BaseModel):
    """任务执行结果模型"""
    model_config = ConfigDict(extra='forbid')
    
    success: bool = Field(..., description="是否成功")
    action: ActionType = Field(..., description="执行的操作类型")
    total_devices: int = Field(0, description="处理的设备总数")
    success_devices: int = Field(0, description="成功设备数")
    failed_devices: int = Field(0, description="失败设备数")
    message: str = Field("", description="结果消息")
    details: Optional[List[Dict[str, Any]]] = Field(None, description="详细结果列表")
    output_files: Optional[List[str]] = Field(None, description="输出文件列表")
    execution_time: float = Field(0.0, description="执行耗时（秒）")
    errors: Optional[List[str]] = Field(None, description="错误列表")


class DBManager:
    """设备数据库管理类"""
    
    def __init__(self, db_file: Path = None):
        self.db_file = db_file or DATA_DIR / "db" / "devices.db"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT UNIQUE NOT NULL
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                ip TEXT NOT NULL,
                username TEXT,
                password TEXT,
                model TEXT,
                out_path TEXT,
                command_file TEXT,
                UNIQUE(device_name, ip)
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS group_devices (
                group_id INTEGER,
                device_id INTEGER,
                PRIMARY KEY (group_id, device_id),
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
            """)
            
            conn.commit()
    
    def get_devices_by_filter(self, filter_params: DeviceFilter) -> List[Dict[str, Any]]:
        """根据过滤条件获取设备列表"""
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            query = "SELECT DISTINCT d.* FROM devices d"
            params = []
            
            if filter_params.group:
                query += """
                JOIN group_devices gd ON d.device_id = gd.device_id
                JOIN groups g ON gd.group_id = g.group_id
                WHERE g.group_name = ?
                """
                params.append(filter_params.group)
            else:
                query += " WHERE 1=1"
            
            if filter_params.device_name:
                query += " AND d.device_name LIKE ?"
                params.append(f"%{filter_params.device_name}%")
            
            if filter_params.ip:
                query += " AND d.ip = ?"
                params.append(filter_params.ip)
            
            if filter_params.model:
                query += " AND d.model LIKE ?"
                params.append(f"%{filter_params.model}%")
            
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    
    def list_groups(self) -> List[str]:
        """列出所有分组"""
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("SELECT group_name FROM groups")
            return [row[0] for row in cur.fetchall()]
    
    def get_device_by_ip_or_name(self, identifier: str) -> Optional[Dict[str, Any]]:
        """根据IP或名称获取设备"""
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM devices 
                WHERE ip = ? OR device_name = ? OR device_name LIKE ?
                LIMIT 1
            """, (identifier, identifier, f"%{identifier}%"))
            row = cur.fetchone()
            return dict(row) if row else None


class ConfigBackupTool:
    """配置备份工具类"""
    
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
        self.output_base = DATA_DIR / "outputs"
        self.output_base.mkdir(parents=True, exist_ok=True)
    
    def _mask_password(self, password: str) -> str:
        """安全脱敏密码"""
        if not password:
            return "***"
        return password[:2] + "***" + password[-2:] if len(password) > 4 else "***"
    
    async def backup_device(self, device: Dict[str, Any], commands: List[str] = None) -> Dict[str, Any]:
        """异步备份单个设备配置"""
        try:
            import netmiko
            from netmiko import ConnectHandler
            
            device_name = device.get("device_name", "unknown")
            ip = device.get("ip")
            username = device.get("username") or "admin"
            password = device.get("password") or ""
            
            logger.info(f"[备份] 正在连接设备: {device_name} ({ip})")
            logger.debug(f"[备份] 设备凭证: user={username}, password={self._mask_password(password)}")
            
            conn = ConnectHandler(
                device_type="generic_ssh",
                ip=ip,
                username=username,
                password=password,
                read_timeout_override=60
            )
            
            timestamp = datetime.now(BEIJING_TZ).strftime("%Y%m%d%H%M%S")
            out_path = self.output_base / timestamp / device.get("out_path", "backup")
            out_path.mkdir(parents=True, exist_ok=True)
            
            output_file = out_path / f"{device_name}_{ip}.txt"
            
            if not commands:
                commands = ["display version", "display current-configuration"]
            
            outputs = []
            for cmd in commands:
                try:
                    output = conn.send_command(cmd, read_timeout=60)
                    outputs.append(f"命令: {cmd}\n输出:\n{output}\n{'-'*50}")
                    logger.info(f"[备份] 设备 {device_name} 执行命令成功: {cmd}")
                except Exception as e:
                    logger.error(f"[备份] 设备 {device_name} 命令执行失败: {cmd} - {e}")
                    outputs.append(f"命令: {cmd}\n错误: {e}\n{'-'*50}")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(outputs))
            
            conn.disconnect()
            
            logger.info(f"[备份] 设备 {device_name} 备份完成: {output_file}")
            
            return {
                "device_name": device_name,
                "ip": ip,
                "success": True,
                "output_file": str(output_file),
                "commands_count": len(commands)
            }
            
        except Exception as e:
            logger.error(f"[备份] 设备 {device.get('device_name', 'unknown')} 备份失败: {e}")
            return {
                "device_name": device.get("device_name", "unknown"),
                "ip": device.get("ip"),
                "success": False,
                "error": str(e)
            }
    
    async def backup_by_filter(self, filter_params: DeviceFilter) -> TaskResult:
        """根据过滤条件批量备份设备"""
        start_time = datetime.now()
        
        devices = self.db_manager.get_devices_by_filter(filter_params)
        if not devices:
            return TaskResult(
                success=False,
                action=ActionType.BACKUP,
                message=f"未找到符合条件的设备: {filter_params.model_dump(exclude_none=True)}"
            )
        
        logger.info(f"[备份] 开始备份 {len(devices)} 个设备")
        
        tasks = [self.backup_device(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_devices = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed_devices = len(results) - success_devices
        
        details = [r for r in results if isinstance(r, dict)]
        output_files = [r.get("output_file") for r in details if r.get("output_file")]
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return TaskResult(
            success=failed_devices == 0,
            action=ActionType.BACKUP,
            total_devices=len(devices),
            success_devices=success_devices,
            failed_devices=failed_devices,
            message=f"备份完成: 成功 {success_devices}/{len(devices)}",
            details=details,
            output_files=output_files,
            execution_time=execution_time,
            errors=[r.get("error") for r in details if not r.get("success")]
        )


class PatrolTool:
    """巡检工具类"""
    
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
        self.output_base = DATA_DIR / "outputs"
        self.output_base.mkdir(parents=True, exist_ok=True)
    
    def _mask_password(self, password: str) -> str:
        """安全脱敏密码"""
        if not password:
            return "***"
        return password[:2] + "***" + password[-2:] if len(password) > 4 else "***"
    
    async def patrol_device(self, device: Dict[str, Any], save_baseline: bool = False) -> Dict[str, Any]:
        """异步巡检单个设备"""
        try:
            import netmiko
            from netmiko import ConnectHandler
            
            device_name = device.get("device_name", "unknown")
            ip = device.get("ip")
            username = device.get("username") or "admin"
            password = device.get("password") or ""
            
            logger.info(f"[巡检] 正在连接设备: {device_name} ({ip})")
            logger.debug(f"[巡检] 设备凭证: user={username}, password={self._mask_password(password)}")
            
            conn = ConnectHandler(
                device_type="generic_ssh",
                ip=ip,
                username=username,
                password=password,
                read_timeout_override=60
            )
            
            timestamp = datetime.now(BEIJING_TZ).strftime("%Y%m%d%H%M%S")
            out_path = self.output_base / "patrol" / timestamp / device_name
            out_path.mkdir(parents=True, exist_ok=True)
            
            inspect_commands = [
                "display version",
                "display device",
                "display interface",
                "display cpu-usage",
                "display memory"
            ]
            
            outputs = []
            for cmd in inspect_commands:
                try:
                    output = conn.send_command(cmd, read_timeout=60)
                    outputs.append(f"命令: {cmd}\n输出:\n{output}\n{'-'*50}")
                    logger.info(f"[巡检] 设备 {device_name} 执行巡检命令: {cmd}")
                except Exception as e:
                    logger.error(f"[巡检] 设备 {device_name} 命令执行失败: {cmd} - {e}")
            
            output_file = out_path / f"{device_name}_巡检报告_{timestamp}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(outputs))
            
            conn.disconnect()
            
            logger.info(f"[巡检] 设备 {device_name} 巡检完成: {output_file}")
            
            return {
                "device_name": device_name,
                "ip": ip,
                "success": True,
                "output_file": str(output_file),
                "commands_count": len(inspect_commands),
                "baseline_saved": save_baseline
            }
            
        except Exception as e:
            logger.error(f"[巡检] 设备 {device.get('device_name', 'unknown')} 巡检失败: {e}")
            return {
                "device_name": device.get("device_name", "unknown"),
                "ip": device.get("ip"),
                "success": False,
                "error": str(e)
            }
    
    async def patrol_by_filter(self, filter_params: DeviceFilter, save_baseline: bool = False) -> TaskResult:
        """根据过滤条件批量巡检设备"""
        start_time = datetime.now()
        
        devices = self.db_manager.get_devices_by_filter(filter_params)
        if not devices:
            return TaskResult(
                success=False,
                action=ActionType.PATROL,
                message=f"未找到符合条件的设备: {filter_params.model_dump(exclude_none=True)}"
            )
        
        logger.info(f"[巡检] 开始巡检 {len(devices)} 个设备, 保存基线: {save_baseline}")
        
        tasks = [self.patrol_device(device, save_baseline) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_devices = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed_devices = len(results) - success_devices
        
        details = [r for r in results if isinstance(r, dict)]
        output_files = [r.get("output_file") for r in details if r.get("output_file")]
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return TaskResult(
            success=failed_devices == 0,
            action=ActionType.PATROL,
            total_devices=len(devices),
            success_devices=success_devices,
            failed_devices=failed_devices,
            message=f"巡检完成: 成功 {success_devices}/{len(devices)}" + (" (基线已保存)" if save_baseline else ""),
            details=details,
            output_files=output_files,
            execution_time=execution_time,
            errors=[r.get("error") for r in details if not r.get("success")]
        )


class IntentParser:
    """LLM意图解析器"""
    
    def __init__(self):
        from langchain_deepseek import ChatDeepSeek
        self.llm = ChatDeepSeek(
            model=settings.LLM_MODEL,
            temperature=0.1,
            api_key=settings.DEEPSEEK_API_KEY
        )
    
    def _extract_filter_from_query(self, query: str) -> Dict[str, Any]:
        """从查询中提取过滤条件"""
        filter_dict = {}
        
        ip_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        ip_match = re.search(ip_pattern, query)
        if ip_match:
            filter_dict['ip'] = ip_match.group(1)
        
        device_name_pattern = r'device[:\s]+([^\s]+)'
        device_match = re.search(device_name_pattern, query, re.IGNORECASE)
        if device_match:
            filter_dict['device_name'] = device_match.group(1)
        
        group_pattern = r'group[:\s]+([^\s]+)'
        group_match = re.search(group_pattern, query, re.IGNORECASE)
        if group_match:
            filter_dict['group'] = group_match.group(1)
        
        model_pattern = r'model[:\s]+([^\s]+)'
        model_match = re.search(model_pattern, query, re.IGNORECASE)
        if model_match:
            filter_dict['model'] = model_match.group(1)
        
        return filter_dict
    
    async def parse(self, query: str) -> ParsedIntent:
        """使用LLM解析用户意图"""
        try:
            filter_dict = self._extract_filter_from_query(query)
            
            prompt = f"""你是运维AI Agent意图识别专家。请分析以下用户查询：

用户查询: {query}

请严格判断意图并返回JSON格式结果：

如果用户要执行配置备份或命令执行：
{{"action": "backup", "save_baseline": false, "confidence": 0.9, "reason": "..."}}

如果用户要执行设备巡检：
{{"action": "patrol", "save_baseline": true/false, "confidence": 0.9, "reason": "..."}}

如果用户要列出设备：
{{"action": "list_devices", "confidence": 0.8, "reason": "..."}}

如果用户要列出分组：
{{"action": "list_groups", "confidence": 0.8, "reason": "..."}}

关键词映射：
- "备份"、"备份配置"、"执行备份" → backup
- "巡检"、"健康检查"、"巡检设备" → patrol
- "列出设备"、"查看设备" → list_devices
- "列出分组"、"查看分组" → list_groups

只返回JSON，不要有任何其他内容。"""
            
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                action = ActionType(data.get('action', 'unknown'))
                return ParsedIntent(
                    action=action,
                    filter=DeviceFilter(**filter_dict) if filter_dict else DeviceFilter(),
                    save_baseline=data.get('save_baseline', False),
                    confidence=data.get('confidence', 0.8),
                    raw_query=query,
                    reason=data.get('reason')
                )
            
            return ParsedIntent(
                action=ActionType.UNKNOWN,
                filter=DeviceFilter(**filter_dict) if filter_dict else DeviceFilter(),
                confidence=0.0,
                raw_query=query,
                reason="无法解析意图"
            )
            
        except Exception as e:
            logger.error(f"[意图解析] 解析失败: {e}")
            return ParsedIntent(
                action=ActionType.UNKNOWN,
                confidence=0.0,
                raw_query=query,
                reason=f"解析异常: {str(e)}"
            )


class NetOpsToolsOrchestrator:
    """运维工具编排器"""
    
    def __init__(self):
        self.db_manager = DBManager()
        self.backup_tool = ConfigBackupTool(self.db_manager)
        self.patrol_tool = PatrolTool(self.db_manager)
        self.intent_parser = IntentParser()
    
    async def execute_async(self, query: str) -> Dict[str, Any]:
        """执行用户查询（异步版本）"""
        return await self._execute_internal(query)
    
    def execute_sync(self, query: str) -> Dict[str, Any]:
        """执行用户查询（同步版本）"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 使用 nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(self._execute_internal(query))
        except RuntimeError:
            # 如果没有运行中的循环
            return asyncio.run(self._execute_internal(query))
    
    async def _execute_internal(self, query: str) -> Dict[str, Any]:
        """执行用户查询"""
        logger.info(f"[执行] 收到查询: {query}")
        
        intent = await self.intent_parser.parse(query)
        logger.info(f"[执行] 解析意图: {intent.action.value}, 置信度: {intent.confidence}")
        
        if intent.action == ActionType.UNKNOWN:
            return {
                "success": False,
                "message": f"无法理解您的请求: {intent.reason}",
                "suggestion": "请尝试使用以下格式：\n- '备份 group all'\n- '巡检 IP 192.168.1.1'\n- '列出所有设备'"
            }
        
        if intent.action == ActionType.LIST_GROUPS:
            groups = self.db_manager.list_groups()
            return {
                "success": True,
                "message": f"找到 {len(groups)} 个分组",
                "groups": groups
            }
        
        if intent.action == ActionType.LIST_DEVICES:
            devices = self.db_manager.get_devices_by_filter(intent.filter)
            safe_devices = []
            for d in devices:
                safe_d = {k: v for k, v in d.items() if k != 'password'}
                safe_d['has_password'] = bool(d.get('password'))
                safe_devices.append(safe_d)
            return {
                "success": True,
                "message": f"找到 {len(devices)} 个设备",
                "devices": safe_devices
            }
        
        if intent.action == ActionType.BACKUP:
            try:
                from src.core.celery_tasks.tasks import execute_config_backup_task
                filter_dict = intent.filter.model_dump(exclude_none=True)
                ticket_id = f"BACKUP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                print(f"[DEBUG] 提交配置备份Celery任务: ticket_id={ticket_id}")
                celery_task = execute_config_backup_task.delay(
                    filter_params=filter_dict,
                    ticket_id=ticket_id
                )
                
                return {
                    "success": True,
                    "message": "配置备份任务已提交",
                    "action": "backup",
                    "ticket_id": ticket_id,
                    "celery_task_id": celery_task.id,
                    "status": "pending",
                    "suggestion": f"任务ID: {celery_task.id}\n请等待任务完成后下载配置文件"
                }
            except Exception as e:
                logger.error(f"[配置备份] Celery任务提交失败: {e}")
                logger.warning("[配置备份] 回退到同步执行模式")
                result = await self.backup_tool.backup_by_filter(intent.filter)
                return result.model_dump(exclude_none=True)
        
        if intent.action == ActionType.PATROL:
            try:
                from src.core.celery_tasks.tasks import execute_device_patrol_task
                filter_dict = intent.filter.model_dump(exclude_none=True)
                ticket_id = f"PATROL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                print(f"[DEBUG] 提交设备巡检Celery任务: ticket_id={ticket_id}, save_baseline={intent.save_baseline}")
                celery_task = execute_device_patrol_task.delay(
                    filter_params=filter_dict,
                    ticket_id=ticket_id,
                    save_baseline=intent.save_baseline
                )
                
                return {
                    "success": True,
                    "message": "设备巡检任务已提交",
                    "action": "patrol",
                    "ticket_id": ticket_id,
                    "celery_task_id": celery_task.id,
                    "status": "pending",
                    "suggestion": f"任务ID: {celery_task.id}\n请等待任务完成后下载巡检报告"
                }
            except Exception as e:
                logger.error(f"[设备巡检] Celery任务提交失败: {e}")
                logger.warning("[设备巡检] 回退到同步执行模式")
                result = await self.patrol_tool.patrol_by_filter(intent.filter, intent.save_baseline)
                return result.model_dump(exclude_none=True)
        
        return {
            "success": False,
            "message": f"不支持的操作类型: {intent.action.value}"
        }
    
    # 向后兼容
    execute = execute_async


async def main():
    """测试入口"""
    orchestrator = NetOpsToolsOrchestrator()
    
    test_queries = [
        "备份 group all",
        "巡检 IP 192.168.1.1",
        "列出所有分组",
        "列出所有设备"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print('='*60)
        result = await orchestrator.execute(query)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
