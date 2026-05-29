---
name: itsm-change-ticket-writer
version: 1.0.0
description: 根据防火墙策略 ZIP/manifest 生成 ITSM 变更工单 Excel
category: itsm
tags:
- itsm
- change
- excel
author: NetOps Team
triggers:
- 生成变更工单
- 编写变更工单
- change ticket
celery_task: execute_itsm_change_ticket_task
execution_mode: async
inputs:
- name: ticket_id
  type: string
  required: true
- name: config_file_key
  type: string
  required: false
- name: config_files_url
  type: string
  required: false
- name: manifest
  type: object
  required: false
outputs:
- name: change_excel
  type: download
  description: 变更工单 Excel
enabled: true
fallback_to_rag: false
---

# ITSM 变更工单编写

根据 `firewall-policy-generator` 产物（manifest 或 ZIP）生成四 Sheet 变更工单 Excel。
