---
name: itsm-callback
version: 1.0.0
description: 将变更工单与策略 ZIP 回调至 ITSM 系统
category: itsm
tags:
- itsm
- callback
author: NetOps Team
entry_script: scripts/itsm_callback.py
entry_output: none
triggers:
- itsm callback
- 回调 ITSM
celery_task: execute_itsm_callback_task
execution_mode: async
inputs:
- name: ticket_id
  type: string
  required: true
- name: callback_url
  type: string
  required: true
- name: change_excel_url
  type: string
  required: false
- name: config_files_url
  type: string
  required: false
outputs:
- name: callback_status
  type: string
enabled: true
fallback_to_rag: false
---

# ITSM 回调

向 ITSM `callback_url` POST 变更结果，附带防火墙 ZIP 与变更工单 Excel 下载链接。

## 执行方式

平台通过 `execute_skill_task` 调用 `scripts/itsm_callback.py`（`entry_output: none`，stdout 返回 JSON）。
