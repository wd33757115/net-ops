#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
device_manager.py
版本：V2（支持每个设备独立用户名和密码）
"""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

DB_FILE = Path("db/devices.db")

class DBManager:
    """SQLite数据库管理类（V2）"""
    def __init__(self, db_file: Path = DB_FILE):
        self.db_file = db_file
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表（全新设计，不做任何迁移）"""
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            # 分组表
            cur.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT UNIQUE NOT NULL
            )
            """)
            # 设备表 - 新增 username 和 password 字段
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
            # 分组-设备关联表
            cur.execute("""
            CREATE TABLE IF NOT EXISTS group_devices (
                group_id INTEGER,
                device_id INTEGER,
                PRIMARY KEY (group_id, device_id),
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
            """)
            # 索引优化
            cur.execute("CREATE INDEX IF NOT EXISTS idx_groups_name ON groups (group_name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_name_ip ON devices (device_name, ip)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_group_devices_gid ON group_devices (group_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_group_devices_did ON group_devices (device_id)")
            conn.commit()

    def import_from_excel(self, excel_path: Path) -> None:
        """从Excel导入设备（支持 username/password 列）"""
        df = pd.read_excel(excel_path)
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            for _, row in df.iterrows():
                device_name = row.get("device_name", "unknown")
                ip = row.get("IP", "unknown")
                username = row.get("username")
                password = row.get("password")
                model = row.get("model")
                out_path = row.get("out_path")
                command_file = row.get("command_file")

                # 插入或更新设备
                cur.execute("""
                INSERT OR REPLACE INTO devices 
                (device_name, ip, username, password, model, out_path, command_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (device_name, ip, username, password, model, out_path, command_file))

                device_id = cur.lastrowid or cur.execute(
                    "SELECT device_id FROM devices WHERE device_name=? AND ip=?", 
                    (device_name, ip)
                ).fetchone()[0]

                # 分组处理
                groups_str = row.get("group", "")
                if groups_str:
                    group_names = [g.strip() for g in groups_str.split(",")]
                    for group_name in group_names:
                        cur.execute("INSERT OR IGNORE INTO groups (group_name) VALUES (?)", (group_name,))
                        group_id_row = cur.execute("SELECT group_id FROM groups WHERE group_name=?", (group_name,)).fetchone()
                        if group_id_row:
                            group_id = group_id_row[0]
                            cur.execute("INSERT OR IGNORE INTO group_devices (group_id, device_id) VALUES (?, ?)", (group_id, device_id))
            conn.commit()

    def get_devices_by_group(self, group_name: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT d.* FROM devices d
            JOIN group_devices gd ON d.device_id = gd.device_id
            JOIN groups g ON gd.group_id = g.group_id
            WHERE g.group_name = ?
            """, (group_name,))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def list_groups(self) -> List[str]:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("SELECT group_name FROM groups")
            return [row[0] for row in cur.fetchall()]

    def delete_group(self, group_name: str) -> None:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
            group_id = cur.fetchone()
            if group_id:
                cur.execute("DELETE FROM group_devices WHERE group_id = ?", (group_id[0],))
                cur.execute("DELETE FROM groups WHERE group_id = ?", (group_id[0],))
                conn.commit()
            else:
                raise ValueError(f"分组 {group_name} 不存在")

    def add_device_to_group(self, group_name: str, device_name: str, ip: str,
                          username: Optional[str] = None,
                          password: Optional[str] = None,
                          model: Optional[str] = None, 
                          out_path: Optional[str] = None, 
                          command_file: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO groups (group_name) VALUES (?)", (group_name,))
            group_id_row = cur.execute("SELECT group_id FROM groups WHERE group_name=?", (group_name,)).fetchone()
            if not group_id_row:
                raise ValueError(f"无法创建分组 {group_name}")
            group_id = group_id_row[0]

            cur.execute("""
            INSERT OR REPLACE INTO devices 
            (device_name, ip, username, password, model, out_path, command_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (device_name, ip, username, password, model, out_path, command_file))
            
            device_id = cur.lastrowid or cur.execute(
                "SELECT device_id FROM devices WHERE device_name=? AND ip=?", 
                (device_name, ip)
            ).fetchone()[0]

            cur.execute("INSERT OR IGNORE INTO group_devices (group_id, device_id) VALUES (?, ?)", (group_id, device_id))
            conn.commit()

    def remove_device_from_group(self, group_name: str, device_id: int) -> None:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
            group_id = cur.fetchone()
            if not group_id:
                raise ValueError(f"分组 {group_name} 不存在")
            cur.execute("DELETE FROM group_devices WHERE group_id = ? AND device_id = ?", (group_id[0], device_id))
            if cur.rowcount == 0:
                raise ValueError(f"设备 ID {device_id} 未在分组 {group_name} 中找到")
            conn.commit()

    def update_device(self, device_id: int, 
                     device_name: Optional[str] = None,
                     ip: Optional[str] = None,
                     username: Optional[str] = None,
                     password: Optional[str] = None,
                     model: Optional[str] = None, 
                     out_path: Optional[str] = None, 
                     command_file: Optional[str] = None) -> None:
        if all(v is None for v in [device_name, ip, username, password, model, out_path, command_file]):
            raise ValueError("至少提供一个要更新的字段")

        updates = []
        params = []
        if device_name is not None:
            updates.append("device_name = ?"); params.append(device_name)
        if ip is not None:
            updates.append("ip = ?"); params.append(ip)
        if username is not None:
            updates.append("username = ?"); params.append(username)
        if password is not None:
            updates.append("password = ?"); params.append(password)
        if model is not None:
            updates.append("model = ?"); params.append(model)
        if out_path is not None:
            updates.append("out_path = ?"); params.append(out_path)
        if command_file is not None:
            updates.append("command_file = ?"); params.append(command_file)
        params.append(device_id)

        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE devices SET {', '.join(updates)} WHERE device_id = ?", params)
            if cur.rowcount == 0:
                raise ValueError(f"设备 ID {device_id} 不存在")
            conn.commit()

def list_devices_by_group(db: DBManager, group_name: str) -> None:
    try:
        devices = db.get_devices_by_group(group_name)
        if not devices:
            print(f"分组 {group_name} 不存在或无设备")
        else:
            print(f"分组 {group_name} 中的设备：")
            for device in devices:
                print(f"- 设备ID: {device['device_id']}, 设备名称: {device['device_name']}, IP: {device['ip']}, "
                      f"用户名: {device.get('username', '[全局]')}, 输出路径: {device.get('out_path', 'N/A')}")
    except ValueError as e:
        print(e)

def main() -> None:
    parser = argparse.ArgumentParser(description="设备管理工具 V2（支持独立用户名密码）")
    parser.add_argument("--import-excel", action="store_true", help="从Excel导入设备和分组到数据库")
    parser.add_argument("--devices", "-p", help="设备Excel文件，用于导入")
    parser.add_argument("--list-groups", action="store_true", help="列出所有分组")
    parser.add_argument("--delete-group", help="删除指定分组")
    parser.add_argument("--list-devices-by-group", help="根据分组名称列出对应设备")
    parser.add_argument("--add-device-to-group", help="添加设备到指定分组")
    parser.add_argument("--device-name", help="设备名称")
    parser.add_argument("--ip", help="设备IP")
    parser.add_argument("--username", help="设备用户名（可选）")
    parser.add_argument("--password", help="设备密码（可选）")
    parser.add_argument("--model", help="设备型号（可选）")
    parser.add_argument("--out-path", help="输出路径（可选）")
    parser.add_argument("--command-file", help="命令文件（可选）")
    parser.add_argument("--remove-device-from-group", help="从指定分组移除设备")
    parser.add_argument("--device-id", type=int, help="设备ID")
    parser.add_argument("--update-device", action="store_true", help="更新设备信息")

    args = parser.parse_args()
    db = DBManager()

    if args.import_excel:
        if not args.devices:
            raise ValueError("--import-excel 需要指定 --devices Excel文件")
        db.import_from_excel(Path(args.devices))
        print("✅ Excel导入完成（已支持每个设备独立用户名和密码）")
        return

    if args.list_groups:
        groups = db.list_groups()
        print("所有分组：")
        for g in groups:
            print(g)
        return

    if args.delete_group:
        try:
            db.delete_group(args.delete_group)
            print(f"分组 {args.delete_group} 已删除")
        except ValueError as e:
            print(e)
        return

    if args.list_devices_by_group:
        list_devices_by_group(db, args.list_devices_by_group)
        return

    if args.add_device_to_group:
        if not args.device_name or not args.ip:
            raise ValueError("--add-device-to-group 需要指定 --device-name 和 --ip")
        try:
            db.add_device_to_group(
                args.add_device_to_group,
                args.device_name,
                args.ip,
                args.username,
                args.password,
                args.model,
                args.out_path,
                args.command_file
            )
            print(f"设备 {args.device_name} ({args.ip}) 已添加到分组 {args.add_device_to_group}")
        except ValueError as e:
            print(e)
        return

    if args.remove_device_from_group:
        if not args.device_id:
            raise ValueError("--remove-device-from-group 需要指定 --device-id")
        try:
            db.remove_device_from_group(args.remove_device_from_group, args.device_id)
            print(f"设备 ID {args.device_id} 已从分组 {args.remove_device_from_group} 中移除")
        except ValueError as e:
            print(e)
        return

    if args.update_device:
        if not args.device_id:
            raise ValueError("--update-device 需要指定 --device-id")
        try:
            db.update_device(
                args.device_id,
                args.device_name,
                args.ip,
                args.username,
                args.password,
                args.model,
                args.out_path,
                args.command_file
            )
            print(f"设备 ID {args.device_id} 已更新")
        except ValueError as e:
            print(e)
        return

    parser.print_help()

if __name__ == "__main__":
    main()