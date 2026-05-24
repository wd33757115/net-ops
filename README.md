
# NetOps Agent — AI 驱动的网络运维平台

基于 LLM 的智能网络运维系统，采用 **Supervisor + N 个 Skill** 架构，支持智能路由、RAG 知识问答、
自动化设备操作、防火墙策略生成等。

## 系统架构

```mermaid
graph TB
    User[用户] --&gt; React[React 前端]
    User --&gt; Django[Django 后端]
    Django --&gt; FastAPI[FastAPI 网关]
    FastAPI --&gt; LangGraph[LangGraph Supervisor]
    LangGraph --&gt; SkillEngine[Skill 系统引擎]
    LangGraph --&gt; KnowledgeQA[知识问答 RAG]
    
    SkillEngine --&gt; SkillRegistry[Skill 注册器]
    SkillEngine --&gt; SemanticRouter[语义路由]
    SkillEngine --&gt; SkillLoader[Skill 加载器]
    
    SkillEngine --&gt; SkillExecutor[Skill 执行器]
    SkillExecutor --&gt; Celery[Celery 任务]
    Celery --&gt; Netmiko[Netmiko 设备操作]
    
    KnowledgeQA --&gt; ChromaDB[ChromaDB]
    ChromaDB --&gt; KnowledgeBase[(知识库文件)]
    
    subgraph "中间件"
        PostgreSQL[(PostgreSQL)]
        Redis[(Redis)]
        RabbitMQ[(RabbitMQ)]
        MinIO[(MinIO)]
        Qdrant[(Qdrant)]
    end
    
    LangGraph --&gt; PostgreSQL
    LangGraph --&gt; Redis
    LangGraph --&gt; RabbitMQ
    LangGraph --&gt; MinIO
    LangGraph --&gt; Qdrant
```

## 架构说明

### 前端展示层
- **React 前端** - 现代化聊天界面（3000 端口）
- **Django 后端** - API 代理和用户管理（8001 端口）

### 核心服务层
- **FastAPI 网关** - REST API + WebSocket 支持（8000 端口）
- **LangGraph Supervisor** - 多代理协调器
- **Skill 系统引擎** - 技能管理和执行
- **知识问答 RAG** - 基于 ChromaDB 的检索增强生成

### 中间件层
- **PostgreSQL** - 主要数据库
- **Redis** - 缓存和会话存储
- **RabbitMQ** - 消息队列
- **MinIO** - 对象存储
- **Qdrant** - 向量数据库

## 内置 Skill（6 个）

| Skill | 分类 | 触发示例 |
|-------|------|----------|
| `device-backup` | network | "备份设备配置" "配置备份" |
| `device-patrol` | network | "执行巡检" "设备巡检" |
| `firewall-policy-generator` | security | "生成防火墙策略" |
| `config-diff-tool` | network | "对比配置" "配置差异" |
| `log-analyzer` | network | "分析日志" "日志分析" |
| `network-topology-analyzer` | network | "网络拓扑分析" |

## 快速开始

### 方式一：Docker Compose（推荐）

#### 1. 环境准备
```bash
git clone &lt;repo-url&gt; &amp;&amp; cd netops-agent
# 确保 .env 文件已配置好 DEEPSEEK_API_KEY 等环境变量
```

#### 2. 启动所有服务
```powershell
cd deployment
docker compose up -d
```

#### 3. 访问应用
| 服务 | 地址 |
|------|------|
| React 前端 | http://localhost:3000 |
| Django 后端 | http://localhost:8001 |
| FastAPI 文档 | http://localhost:8000/docs |
| MinIO 控制台 | http://localhost:9001 (minioadmin/minioadmin) |
| RabbitMQ 管理 | http://localhost:15672 (guest/guest) |

### 方式二：PowerShell 脚本

#### 1. 环境准备
```bash
git clone &lt;repo-url&gt; &amp;&amp; cd netops-agent
pip install -r requirements.txt
# 确保 .env 文件已配置
```

#### 2. 一键启动
```powershell
.\start_all.ps1
```

#### 3. 一键停止
```powershell
.\stop_all.ps1
```

## 创建新 Skill

### CLI 一键创建

```bash
# 基本创建
python scripts/create_skill.py -n my-skill -d "我的新技能"

# 完整参数
python scripts/create_skill.py -n my-skill -d "巡检新功能" \
    -c network -t "执行巡检" "设备巡检" --tags inspection device

# 交互模式
python scripts/create_skill.py --interactive
```

### SKILL.md 格式（v2.0）

```markdown
---
name: my-skill
version: 1.0.0
description: 技能描述
category: network
tags: [tag1, tag2]
triggers:
  - "触发词1"
  - "触发词2"
inputs:
  - name: param1
    type: string
    required: true
    description: 参数描述
outputs:
  - name: result
    type: text
    description: 输出描述
enabled: true
fallback_to_rag: true
---

# 技能名称

技能描述正文。

## 核心原则
1. 参数验证：执行前验证所有必填参数
2. 幂等性：相同输入产生相同输出
3. 超时控制：单次执行超过 300s 视为失败

## 核心能力
1. 能力一
2. 能力二

## 工作流程
1. 参数确认 → 2. 任务执行 → 3. 结果处理 → 4. 报告输出

## 输出格式
## 安全规范
## 示例
## 注意事项
```

### 验证 Skill 格式

```bash
# 验证所有 Skill
python scripts/validate_skill.py --all

# 验证单个
python scripts/validate_skill.py src/skills/my-skill/SKILL.md

# CI/CD JSON 输出
python scripts/validate_skill.py --all --json
```

## 项目结构

```
netops-agent/
├── src/
│   ├── skill_system/          # Skill 核心引擎
│   │   ├── __init__.py        # SkillSystem 主类
│   │   ├── metadata.py        # SKILL.md 解析 + v2.0 模板
│   │   ├── router.py          # 3 阶段语义路由
│   │   ├── loader.py          # Progressive Disclosure 加载器
│   │   ├── cache.py           # LRU 缓存 (metadata/instructions/embedding)
│   │   └── security.py        # 权限控制 + 审计日志
│   ├── skills/                # 6 个内置 Skill (SKILL.md 文件驱动)
│   ├── agents/supervisor/     # LangGraph Supervisor (3-Node StateGraph)
│   ├── common/                # logger / metrics / retry / tracing
│   ├── core/                  # Celery tasks / RAG service
│   ├── gateway/               # FastAPI + WebSocket
│   └── infrastructure/        # PostgreSQL / MinIO
├── web/
│   ├── react_frontend/        # React 前端应用
│   └── django_backend/        # Django 后端应用
├── scripts/
│   ├── create_skill.py        # Skill Creator CLI
│   └── validate_skill.py      # Skill 格式验证工具
├── tests/                     # 统一测试目录
│   └── skill_system/          # 7 个测试文件, 62 个用例
├── docs/                      # 文档 + ADR
│   ├── adr/                   # 架构决策记录
│   └── SKILL_CREATION_GUIDE.md
├── knowledge_base/            # RAG 知识库文件
├── deployment/                # Docker 配置
│   ├── docker-compose.yml
│   ├── Dockerfile.fastapi
│   ├── Dockerfile.django
│   └── Dockerfile.react
├── start_all.ps1              # 一键启动脚本
└── stop_all.ps1               # 一键停止脚本
```

## 测试

```bash
# 运行所有 Skill 系统测试（62 个用例）
python tests/skill_system/test_cache.py      # LRU 缓存
python tests/skill_system/test_security.py   # 权限 + 审计
python tests/skill_system/test_metadata.py   # SKILL.md 解析
python tests/skill_system/test_router.py     # 语义路由
python tests/skill_system/test_loader.py     # 加载器
python tests/skill_system/test_init.py       # SkillSystem 集成
python tests/skill_system/test_e2e.py        # E2E 集成

# 格式验证
python scripts/validate_skill.py --all        # 所有 Skill 通过
```

## 关键设计原则

- **Metadata 常驻** — 只把 name + description 常驻内存
- **Progressive Disclosure** — 只有匹配的 Skill 正文才注入上下文（800-1500 tokens）
- **指令注入而非函数调用** — Skill = 一套专业规则，而非单个 tool
- **文件系统驱动** — Skill = 目录 + SKILL.md（Git 版本管理友好）
- **3 层容错** — 加载失败 → 降级, 路由失败 → RAG 兜底, 执行异常 → RAG 兜底

## 文档

- [Skill 创建指南](docs/SKILL_CREATION_GUIDE.md)
- [架构决策记录](docs/adr/)
- [启动手册](docs/启动手册.md)
- [测试手册](docs/测试手册.md)
- [Web 开发文档](web/README.md)

## License

MIT
