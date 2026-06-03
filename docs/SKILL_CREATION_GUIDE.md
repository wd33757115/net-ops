<!-- SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->


# Skill 创建指南 (v2.0)

本指南详细介绍如何为 NetOps Agent 创建符合标准化格式的 Skill。

## 目录

1. [什么是 Skill](#什么是-skill)
2. [5 秒快速创建](#5-秒快速创建)
3. [SKILL.md v2.0 标准格式](#skillmd-v20-标准格式)
4. [必填章节详解](#必填章节详解)
5. [Frontmatter 字段说明](#frontmatter-字段说明)
6. [完整示例](#完整示例)
7. [验证与调试](#验证与调试)

---

## 什么是 Skill

Skill 是可重用的能力模块，通过 **一个 `SKILL.md` 文件** 即可完整定义。系统启动时自动扫描 `src/skills/` 目录下所有子文件夹中的 `SKILL.md` 文件。

### 设计理念

- **文件驱动** — 无需写代码，Markdown 即 Skill
- **Git 友好** — 纯文本文件，便于版本控制和协作评审
- **Progressive Disclosure** — 启动时只加载元数据，匹配时才加载完整指令（800-1500 tokens）
- **3 阶段路由** — 触发词匹配 → Embedding 语义匹配 → LLM Judge 精准判断

---

## 5 秒快速创建

```bash
# CLI 一键创建
python scripts/create_skill.py -n my-skill -d "我的新技能" -c network

# 交互模式（5 步引导）
python scripts/create_skill.py --interactive

# 验证格式
python scripts/validate_skill.py src/skills/my-skill/SKILL.md
```

---

## SKILL.md v2.0 标准格式

```yaml
---
name: my-skill              # 必填: kebab-case 唯一标识
version: 1.0.0              # 必填: semver 版本号
description: 技能简短描述     # 必填: 一句话说明
category: network            # 必填: network|security|compute|storage|monitoring|general
tags: [tag1, tag2]           # 推荐: 标签列表
author: NetOps Team          # 推荐: 作者
triggers:                    # 必填: 触发词列表（建议 2-5 个）
  - "触发词1"
  - "触发词2"
inputs:                      # 推荐: 输入参数定义
  - name: param1
    type: string
    required: true
    description: 参数描述
outputs:                     # 推荐: 输出格式定义
  - name: result
    type: text
    description: 输出描述
references:                  # 可选: 外部引用
  - type: rag
    source: knowledge-base
    description: 知识源描述
enabled: true                # 必填: 是否启用
fallback_to_rag: true        # 必填: 失败后是否走 RAG 兜底
---

# 技能标题

简短介绍。

## 核心原则
## 核心能力
## 工作流程
## 输入参数说明
## 输出格式
## 安全规范
## 示例
## 注意事项
```

---

## 必填章节详解

### `## 核心原则` (必填)

6 条硬性规则，LLM 执行时必须遵守：

```markdown
## 核心原则

1. **参数验证**：执行前必须验证所有必填参数，缺失时向用户明确提示
2. **幂等性**：相同输入应产生相同输出，避免副作用
3. **超时控制**：单次执行超过 300 秒视为失败，触发 RAG 兜底
4. **错误处理**：执行失败时必须提供明确的错误原因和建议
5. **不编造数据**：缺失参数或文件不得编造，必须如实告知用户
6. **安全第一**：涉及设备配置变更时，优先 dry-run 或生成可审查脚本
```

### `## 核心能力` (必填)

该 Skill 的 3 项核心能力，每项附带简短说明：

```markdown
## 核心能力

1. **能力名称**：能力描述
2. **能力名称**：能力描述
3. **能力名称**：能力描述
```

### `## 工作流程` (必填)

4 步执行流程：

```markdown
## 工作流程

1. **参数确认**：验证用户提供的参数是否完整有效
2. **任务执行**：执行核心操作
3. **结果处理**：收集和处理执行结果
4. **报告输出**：格式化输出结果并反馈用户
```

### `## 输出格式` (必填)

期望的输出 JSON Schema：

```markdown
## 输出格式

```json
{
  "success": true,
  "message": "执行结果描述",
  "data": {}
}
```
```

### `## 安全规范` (推荐)

```markdown
## 安全规范

1. **凭证安全**：所有设备凭证通过环境变量获取，不得硬编码
2. **操作审计**：每次执行记录审计日志
3. **权限控制**：根据用户权限级别判断是否允许执行
4. **敏感信息过滤**：日志和返回结果中过滤密码、Token 等
```

### `## 示例` (必填)

至少一个输入/输出示例：

```markdown
## 示例

**输入**："帮我备份生产环境的所有设备"

**输出**：返回备份文件下载链接和统计报告
```

### `## 注意事项` (必填)

```markdown
## 注意事项

- 执行前请确认操作范围和影响
- 变更类操作建议先在测试环境验证
- 超时或失败时自动触发 RAG 知识库兜底
```

---

## Frontmatter 字段说明

### 必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | kebab-case 唯一标识，如 `device-backup` |
| `version` | string | semver 格式，如 `1.0.0` |
| `description` | string | 一句话描述（将显示在 UI 列表和路由 prompt 中） |
| `category` | string | `network` / `security` / `compute` / `storage` / `monitoring` / `general` |
| `triggers` | string[] | 触发关键词列表，建议 2-5 个，含中英文 |
| `enabled` | boolean | `true` 启用，`false` 则路由时自动排除 |
| `fallback_to_rag` | boolean | 执行失败是否自动回退到 RAG 知识库 |

### 推荐字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `tags` | string[] | 标签，辅助关键词匹配 |
| `author` | string | 作者 |
| `inputs` | object[] | 输入参数定义 |
| `outputs` | object[] | 输出格式定义 |

### inputs 子字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 参数名 |
| `type` | string | `string` / `file` / `int` / `float` / `bool` |
| `required` | boolean | 是否必填 |
| `description` | string | 参数说明 |

### outputs 子字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 输出名 |
| `type` | string | `text` / `download` / `json` |
| `description` | string | 输出说明 |

---

## 完整示例

### Celery 任务型 Skill（设备备份）

```markdown
---
name: device-backup
version: 1.0.0
description: 设备配置备份专家
category: network
tags: [backup, device]
triggers:
  - "备份设备配置"
  - "配置备份"
  - "保存配置"
inputs:
  - name: device_name
    type: string
    required: false
    description: 设备名称
  - name: group_name
    type: string
    required: false
    description: 分组名称
outputs:
  - name: backup_files
    type: download
    description: 备份文件压缩包
  - name: backup_report
    type: text
    description: 备份报告
enabled: true
fallback_to_rag: true
---

# 设备配置备份专家

执行网络设备的配置备份操作。

## 核心原则

1. **参数验证**：执行前必须验证至少提供了一个过滤条件
2. **幂等性**：重复执行相同备份请求不会产生副作用
3. **超时控制**：单次备份任务超过 300 秒视为失败
4. **不编造数据**：设备不存在时如实报告
5. **安全第一**：备份内容加密存储，下载链接设置有效期

## 核心能力

1. **多维度过滤**：按设备名称/IP/分组/型号过滤
2. **批量执行**：支持同时备份多台设备
3. **结果报告**：提供备份状态统计和下载链接

## 工作流程

1. **参数确认**：确定备份范围
2. **任务提交**：调用 Celery 任务执行备份
3. **结果处理**：收集备份结果
4. **报告输出**：提供下载链接和统计

## 输出格式

```json
{
  "success": true,
  "message": "备份任务已完成",
  "data": {"task_id": "...", "backup_files": "下载链接"}
}
```

## 安全规范

1. 设备登录凭证通过环境变量获取，不得硬编码
2. 每次备份记录审计日志
3. 只有 POWER_USER 及以上级别可执行
4. 备份报告中自动过滤密码、密钥

## 示例

**输入**："帮我备份生产环境的所有设备"

**输出**：备份文件压缩包下载链接

## 注意事项

- 备份前确认设备在线且可 SSH 连接
- 备份文件保存期限 30 天
- 失败时自动触发 RAG 兜底
```

---

## 验证与调试

### 1. 格式验证

```bash
# 单文件验证
python scripts/validate_skill.py src/skills/my-skill/SKILL.md

# 全量验证
python scripts/validate_skill.py --all

# CI/CD JSON 输出
python scripts/validate_skill.py --all --json --strict
```

### 2. 程序中验证加载

```python
from src.skill_system import get_skill_system

ss = get_skill_system()
skills = ss.list_all_skills()
for s in skills:
    print(f"{s.name}  enabled={s.enabled}")

# 测试路由
matches = ss.route("备份设备配置")
for m in matches:
    print(f"  {m.skill_name}  confidence={m.confidence}  {m.reason}")

# 获取指令
instructions = ss.get_skill_instructions("device-backup")
print(instructions[:200])
```

### 3. UI 中管理

打开 Streamlit UI → **Skills** Tab：
- 查看所有 Skill 列表（状态、触发词、内容预览）
- Create Tab 可视化创建新 Skill
- Validate Tab 一键验证所有 Skill 格式

---

## 常见问题

**Q: 如何让 Skill 匹配更精准？**
A: triggers 建议 2-5 个，包含中英文；description 要有具体特征词；tags 辅助关键词匹配。

**Q: 我的 Skill 是纯 LLM 推理，不需要 Celery，怎么处理？**
A: 省略 `实际执行说明` 章节即可，系统自动识别为 LLM 推理型 Skill。

**Q: 如何热更新 Skill？**
A: Streamlit UI → Skills Tab → 点击 Reload；或代码 `ss.reload_all()`。

**Q: 禁用的 Skill 会怎样？**
A: 路由自动排除，不会出现在匹配结果中。`enabled: false` 即可。
