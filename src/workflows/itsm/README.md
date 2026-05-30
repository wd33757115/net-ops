# ITSM Workflow 插件开发指南

新增一类 ITSM 工单时，**无需修改** `engine.py`、`main.py` 业务逻辑或 Celery 任务实现。只需在 `src/workflows/itsm/<插件名>/` 下添加插件包，并实现对应 Skill 脚本。

## 目录结构

```
src/workflows/itsm/<plugin-name>/
├── WORKFLOW.yaml        # 多步编排定义（Skill 链 + 表达式输入）
├── ITSM.webhook.yaml    # 可选：ITSM Webhook 路由与 context 映射
└── CHAT.intent.yaml     # 可选：聊天触发规则
```

对应 Skill 放在 `src/skills/<skill-name>/`，需包含：

- `SKILL.md`：声明 `entry_script`、`entry_output`（`file` | `dir` | `none`）
- `scripts/<入口>.py`：CLI 入口，支持 `--params params.json`，stdout 末行输出 JSON

## 1. WORKFLOW.yaml

```yaml
name: my-itsm-workflow
description: 示例 ITSM 流程
version: "1.0"

steps:
  - name: step_one
    skill: my-skill-a
    inputs:
      ticket_id: ${context.ticket_id}
      workflow_run_id: ${run.id}

  - name: step_two
    skill: my-skill-b
    inputs:
      ticket_id: ${context.ticket_id}
      prev_result: ${steps.step_one.result.some_field}
      file_key: ${steps.step_one.artifacts.config_zip.file_key}

on_complete:
  message: 流程已完成
  notification:
    title: "工单完成 ({context.ticket_id})"
    body: "所有步骤已执行。"
    level: success
```

### 表达式

| 表达式 | 含义 |
|--------|------|
| `${context.ticket_id}` | Webhook/聊天写入的运行上下文 |
| `${run.id}` | 当前 Workflow Run ID |
| `${steps.<step_name>.result.*}` | 某步 Skill 返回 JSON |
| `${steps.<step_name>.artifacts.<key>.*}` | 某步上传 MinIO 后的 artifact |

## 2. ITSM.webhook.yaml

```yaml
route_key: my-ticket-type
workflow: my-itsm-workflow
accepted_message: 已受理，正在处理
legacy_paths:
  - /api/v1/itsm/webhook/my-ticket-type

context_mapping:
  ticket_id: ticket_id
  ticket_title: ticket_title
  policy_file_url: policy_file.url
  callback_url: callback_url
```

Webhook 入口：`POST /api/v1/itsm/webhook/{route_key}`

平台在启动时扫描所有 `ITSM.webhook.yaml`，自动注册路由。

## 3. CHAT.intent.yaml

```yaml
workflow: my-itsm-workflow
auto_if_source:
  - itsm_webhook
require_any:
  - 防火墙
  - 变更工单
require_all: []
require_any_secondary: []
```

Supervisor 通过 `match_chat_workflow()` 匹配；`auto_if_source` 表示 Webhook 触发的会话自动走 Workflow，无需关键词。

## 4. Skill 脚本约定

入口脚本由平台 `execute_skill()` subprocess 调用：

```bash
python scripts/run.py --params /tmp/params.json --output-dir /tmp/out
# 或 file 模式：-o /tmp/output.xlsx
```

- 平台会将 URL/MinIO `file_key` 下载为本地路径后再写入 `params.json`
- stdout **最后一行**必须是 JSON，例如 `{"success": true, "manifest": {...}}`
- 防火墙类 Skill 可在 JSON 中带 `_local_zip` 路径，平台会上传 MinIO 并填充 `artifacts`

## 5. 验证

```powershell
.\scripts\test\stop.ps1
.\scripts\test\start.ps1
.\venv\Scripts\python.exe -m pytest tests/unit/test_workflow_plugins.py tests/unit/test_itsm_webhook_plugins.py -q
.\venv\Scripts\python.exe .\scripts\test\e2e_itsm_workflow.py
```

## 参考实现

防火墙变更完整示例：`src/workflows/itsm/itsm-firewall-change/`

- Skill：`firewall-policy-generator`、`itsm-change-ticket-writer`、`itsm-callback`
