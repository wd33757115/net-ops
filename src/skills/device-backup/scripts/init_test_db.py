# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "data" / "db" / "devices.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path)
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

test_groups = ['生产环境', '测试环境', 'DMZ区域']
for g in test_groups:
    try:
        cur.execute('INSERT INTO groups (group_name) VALUES (?)', (g,))
        print(f'添加分组: {g}')
    except Exception as e:
        print(f'分组 {g} 已存在或添加失败: {e}')

test_devices = [
    ('核心交换机1', '192.168.1.1', 'admin', 'admin123', 'H3C S5500', 'backup/core'),
    ('核心交换机2', '192.168.1.2', 'admin', 'admin123', 'H3C S5500', 'backup/core'),
    ('接入交换机1', '192.168.2.1', 'admin', 'admin123', 'Huawei S5700', 'backup/access'),
    ('Web服务器1', '192.168.10.1', 'root', 'pass123', 'Dell R720', 'backup/server'),
    ('防火墙1', '192.168.0.1', 'admin', 'firewall123', 'H3C F1000', 'backup/fw'),
]

for device in test_devices:
    try:
        cur.execute('''
            INSERT INTO devices (device_name, ip, username, password, model, out_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', device)
        print(f'添加设备: {device[0]} ({device[1]})')
    except Exception as e:
        print(f'设备 {device[0]} 已存在或添加失败: {e}')

cur.execute('SELECT group_id FROM groups WHERE group_name = ?', ('生产环境',))
row = cur.fetchone()
group_id = row[0] if row else None

if group_id:
    cur.execute('SELECT device_id FROM devices LIMIT 3')
    for row in cur.fetchall():
        device_id = row[0]
        try:
            cur.execute('INSERT INTO group_devices (group_id, device_id) VALUES (?, ?)', (group_id, device_id))
            print(f'关联设备ID {device_id} 到分组 生产环境')
        except:
            pass

conn.commit()
conn.close()

print(f'\n数据库初始化完成: {db_path}')
print(f'数据库包含 {len(test_groups)} 个分组和 {len(test_devices)} 个设备')
