---
name: llm-result-analyzer
version: 1.0.0
description: 读取上游 Skill/Workflow 步骤的结构化结果，调用 LLM 生成分析报告
category: analysis
tags:
- llm
- analysis
- workflow
- report
author: NetOps Team
domain: general
celery_queue: netops.default
min_permission_level: user
rollout_status: stable
enabled_ratio: 100
min_platform_version: "1.0.0"
entry_script: scripts/run.py
entry_output: file
triggers:
- LLM 分析
- 分析结果
- 结果分析
- analyze result
execution_mode: async
inputs:
- name: ticket_id
  type: string
  required: false
- name: prev_result
  type: object
  required: false
  description: 上游步骤完整 result（Workflow ${steps.x.result}）
- name: upstream_result
  type: object
  required: false
  description: 与 prev_result 等价别名
- name: manifest
  type: object
  required: false
  description: 可直接传入 manifest 进行分析
- name: analysis_prompt
  type: string
  required: false
  description: 用户分析问题/指令
- name: analysis_focus
  type: string
  required: false
  description: summary | risk | compliance 或自定义说明
- name: source_step
  type: string
  required: false
  description: 上游步骤名（审计用）
outputs:
- name: analysis
  type: text
  description: Markdown 分析报告
- name: analysis_json
  type: object
  description: 结构化元数据
enabled: true
fallback_to_rag: false
---

# LLM 结果分析 Skill（模式 A）

作为 **Workflow 第三步** 或 Supervisor 链末步，读取前两步产物（JSON / manifest / artifact 元数据），调用 LLM 生成运维分析报告。

## Workflow 接入示例

```yaml
  - name: llm_analysis
    label: LLM 结果分析
    skill: llm-result-analyzer
    inputs:
      ticket_id: ${context.ticket_id}
      prev_result: ${steps.change_ticket.result}
      analysis_prompt: ${context.analysis_prompt}
      analysis_focus: summary
      source_step: change_ticket
      workflow_run_id: ${run.id}
```

## CLI

```bash
python scripts/run.py --params params.json -o /tmp/analysis.md
```

stdout 末行 JSON：`{"success": true, "analysis": "...", ...}`

## 输入优先级

1. `prev_result` / `upstream_result`
2. `{upstream-skill}_output`（Supervisor depends_on 注入）
3. `manifest` 或含 devices/scripts 的扁平 dict
