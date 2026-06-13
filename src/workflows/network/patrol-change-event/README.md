# Patrol Change Event Workflow

组合三个独立 Skill：

```text
device-patrol -> change-detector -> event-builder
```

启动 context 示例：

```json
{
  "filter_params": {
    "group": "生产环境"
  },
  "ticket_id": "PATROL-20260613",
  "save_baseline": false,
  "publish_events": true
}
```

职责边界：

- `device-patrol` 采集设备数据并写入 Snapshot Store。
- `change-detector` 使用 `snapshot_run_id` 对比最近历史快照。
- `event-builder` 读取当前 run 的 Changes 并生成 Events。
- Workflow 只负责编排和参数传递。

