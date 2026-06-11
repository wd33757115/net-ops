---
name: textfsm-generator
version: 1.1.0
description: 从聊天直输 CLI 或 SQLite 巡检原始输出生成并验证 TextFSM 模板，构建 Parser 资产库
category: network
tags:
  - textfsm
  - parser
  - template
  - network
  - automation
author: wangdong
domain: network
min_permission_level: user
rollout_status: stable
enabled_ratio: 100
min_platform_version: "1.0.0"
entry_script: scripts/run.py
entry_output: none
triggers:
  - 生成 TextFSM
  - 生成TEXTFSM
  - TextFSM 模板
  - TextFSM解析模板
  - 解析模板生成
  - textfsm generator
  - Parser 资产
  - display fan
  - 风扇状态
  - 解析 CLI 输出
inputs:
  - name: user_query
    type: string
    required: false
    description: 聊天中粘贴的完整内容（设备提示符 + 命令 + CLI 回显），与 raw_output 等价
  - name: raw_output
    type: string
    required: false
    description: 用户直输的 CLI 原始输出，可含命令首行
  - name: cli_output
    type: string
    required: false
    description: raw_output 别名
  - name: command
    type: string
    required: false
    description: 命令，如 display fan；若 user_query 已含命令可省略
  - name: vendor
    type: string
    required: false
    description: 设备厂商，直输模式未指定时按 display/show 推断
  - name: model
    type: string
    required: false
    description: 设备型号，直输默认 Generic；保存模板目录用 model_slug
  - name: category
    type: string
    required: false
    description: 强制指定字段类别（如 fan），否则查 command_mapping
  - name: patrol_db
    type: string
    required: false
    description: 巡检 SQLite 路径，默认 db/patrol.db（无直输时启用）
  - name: devices_db
    type: string
    required: false
    description: 设备库 SQLite 路径，默认 db/devices.db
  - name: templates_dir
    type: string
    required: false
    description: 模板输出目录，默认项目根 templates/
  - name: max_retries
    type: integer
    required: false
    description: 验证失败自动修复最大重试次数，默认 3
  - name: dry_run
    type: boolean
    required: false
    description: 为 true 时验证通过但不写入模板文件
  - name: use_semantic_extraction
    type: boolean
    required: false
    description: 默认 true；用 LLM 从自然语言理解 vendor/model（非关键词硬编码）
  - name: force_generate
    type: boolean
    required: false
    description: 直输模式默认 true（覆盖已有模板）；数据库模式默认 false
outputs:
  - name: parsed_records
    type: object
    description: 用生成或已有模板解析出的结构化记录（如 slot/fan/state）
  - name: reports
    type: object
    description: 每条 (vendor, model, command) 的验证报告
  - name: summary_path
    type: string
    description: 汇总报告 JSON 路径
  - name: mode
    type: string
    description: direct（聊天直输）或 database（SQLite 扫描）
enabled: true
fallback_to_rag: false
---

# TextFSM Generator

独立 **Parser 资产生成** Skill，支持两种数据来源：

1. **聊天直输（推荐）**：用户在对话中粘贴设备命令与 CLI 回显，即时生成模板并返回结构化结果
2. **SQLite 扫描**：从巡检库发现「有 raw、无 structured」的记录批量生成

## 聊天直输示例

用户输入：

```
<XA-FOTIC-Ant-SW>display fan
 Slot 1:
 Fan 1:
 State    : Normal
 ...
 Fan 4:
 State    : Normal
```

Supervisor 将全文传入 `user_query`（或 `raw_output`）。Skill 将：

1. 识别命令 `display fan`
2. 映射 category `fan` → 字段 `slot`, `fan`, `state`
3. LLM 生成 TextFSM → 四层验证 → 保存模板
4. 返回 `parsed_records`（各风扇状态）

可选参数：`vendor=Huawei`、`model=S5700`、`category=fan`

**厂商/型号识别（语义，非硬编码）**：默认启用 LLM 从自然语言理解设备信息，例如：

- `华三核心 S5590` → vendor=H3C, model=S5590
- `品牌H3C,型号S5590` → vendor=H3C, model=S5590
- `Cisco 9300 的 show cpu` → vendor=Cisco, model=9300

LLM 会参考 `command_mapping.yaml` 中已有设备档案拼写，但**不会**写死「品牌/型号」关键词规则。未提及则 vendor/model 为空，再按 CLI 命令兜底（display→Huawei）。可设 `use_semantic_extraction=false` 关闭。

## 核心原则

1. **参数验证**：直输模式至少需要 user_query / raw_output / cli_output 之一
2. **字段受控**：LLM 不得自由命名字段，必须查 command_mapping → command_categories
3. **四层验证**：编译 → 解析(record>0) → 必填字段 → 值合法性
4. **自动修复**：验证失败将错误反馈 LLM，最多重试 3 次
5. **不编造**：无法识别命令或类别时如实报告并跳过
6. **路径兼容**：模板保存为 `templates/{model_slug}/{command_slug}.textfsm`，与 device-patrol 一致

## 架构约束

1. **禁止修改** `device-patrol`
2. **禁止** device-patrol 调用本 Skill
3. SQLite 模式 **只读** 数据库
4. 配置驱动，不写死单一 Skill 依赖

## 工作流程

**直输模式**（存在 user_query / raw_output / cli_output）：

```
粘贴 CLI → 解析 command + 输出体 → mapping → LLM → 验证 → 保存 → parsed_records
```

**数据库模式**（无直输文本）：

```
SQLite 发现缺失 → 去重 → 同上
```

## 字段类别 fan


| 字段    | 说明          |
| ----- | ----------- |
| slot  | 槽位，如 1      |
| fan   | 风扇编号，如 1    |
| state | 状态，如 Normal |


## 输出格式

```json
{
  "success": true,
  "mode": "direct",
  "parsed_records": [
    {"slot": "1", "fan": "1", "state": "Normal"}
  ]
}
```

## 安全规范

1. 直输内容仅用于生成模板，不连接任何设备
2. 不在日志中输出敏感凭证
3. 生成的模板写入 `templates/`，可人工复核

## 注意事项

- 依赖 `textfsm` 与 `DEEPSEEK_API_KEY`
- 模板路径：`templates/{model_slug}/display_fan.textfsm`（兼容 device-patrol）

