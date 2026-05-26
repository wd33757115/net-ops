# NetOps 部署脚本

本目录提供**测试环境**与**生产环境**的安装、启动、关闭脚本。

## 测试环境（本地开发）

适用于 Windows 本地联调：Docker 跑中间件，应用进程本地热重载。

| 脚本 | 说明 |
|------|------|
| `scripts/test/install.ps1` | 创建 venv、安装 Python/npm 依赖、拉取中间件镜像 |
| `scripts/test/start.ps1` | 启动中间件 + FastAPI + Django + React |
| `scripts/test/stop.ps1` | 停止本地进程与中间件 |
| `scripts/test/e2e_supervisor_v2.ps1` | 经 Django BFF 做 Supervisor v2 三类联调 |

```powershell
# 首次
.\scripts\test\install.ps1

# 启动（默认 USE_SUPERVISOR_V2=true）
.\scripts\test\start.ps1

# 联调
.\scripts\test\e2e_supervisor_v2.ps1

# 关闭
.\scripts\test\stop.ps1
```

中间件 Compose 文件：`deployment/docker-compose.middleware.yml`

日志与 PID：`.runtime/test/logs/`、`.runtime/test/pids.json`

## 生产环境（全 Docker）

| 脚本 | 说明 |
|------|------|
| `scripts/prod/install.ps1` | Windows：拉镜像、构建 django/react |
| `scripts/prod/start.ps1` | Windows：docker compose up -d + migrate |
| `scripts/prod/stop.ps1` | Windows：docker compose down |
| `scripts/prod/install.sh` | Linux：同上 |
| `scripts/prod/start.sh` | Linux：同上 |
| `scripts/prod/stop.sh` | Linux：同上（`--volumes` 删卷） |

```powershell
.\scripts\prod\install.ps1
.\scripts\prod\start.ps1
.\scripts\prod\stop.ps1
```

```bash
chmod +x scripts/prod/*.sh
./scripts/prod/install.sh
./scripts/prod/start.sh
./scripts/prod/stop.sh
```

Compose 文件：`deployment/docker-compose.yml`

## 环境变量

| 变量 | 测试默认 | 生产建议 |
|------|----------|----------|
| `USE_SUPERVISOR_V2` | `true` | `true` |
| `ENFORCE_BFF_ORIGIN` | `false` | `true` |
| `DEBUG` | `true` | `false` |

## 自动化测试

```powershell
# PowerShell 脚本语法校验（Windows 5.1 需 UTF-8 BOM，已内置）
.\scripts\validate_ps1.ps1

# Supervisor v2 图流程（Mock LLM，无需 API Key）
venv\Scripts\python.exe -m pytest tests/agents/test_graph_v2.py tests/integration/test_supervisor_v2_e2e.py -v
```

## 常见问题

1. **`﻿<#` 无法识别 / param 赋值无效**：不要用 UTF-8 BOM；不要用文件头 `<# ... #>` 块注释。请拉取最新脚本（已改为 `#` 行注释 + UTF-8 无 BOM）。
2. **正确执行方式**：`.\scripts\validate_ps1.ps1`（不要用点号源入 `. .\scripts\...`）。
3. **控制台中文乱码**：可 `chcp 65001`，不影响脚本执行。
4. **Docker 未启动**：先开 Docker Desktop，或 `.\scripts\test\start.ps1 -SkipMiddleware`。
