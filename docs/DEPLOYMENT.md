# NetOps Agent Docker 部署指南

## 概述

本指南说明如何使用 Docker 和 Docker Compose 部署 NetOps Agent。

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      React 前端 (Nginx)                            │
│                    http://localhost:3000                        │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Django 后端                            │
│                  http://localhost:8001                        │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI 网关                         │
│                  http://localhost:8000                        │
└────────────┬────────────────────────────────────────────────┘
           │
           ├─────────┬─────────┬─────────┬─────────┐
           │         │         │         │
           ▼         ▼         ▼         ▼
    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
    │ Postgres │  │  Redis  │  │ MinIO  │  │ Qdrant │
    └────────┘  └────────┘  └────────┘  └────────┘
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| React 前端 | 3000 | 用户界面 |
| Django 后端 | 8001 | 后端API代理 |
| FastAPI 网关 | 8000 | AI/Agent 核心 |
| Langfuse | 3001 | 监控与追踪 |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存/任务队列 |
| RabbitMQ | 5672 | 消息队列 |
| RabbitMQ 管理界面 | 15672 | RabbitMQ 管理界面 |
| MinIO | 9000/9001 | 对象存储 |
| Qdrant | 6333 | 向量数据库 |

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 内存
- 至少 10GB 磁盘空间

## 快速部署

### 方法一：使用 Makefile（推荐）

```bash
# 1. 构建并启动所有服务
make -C deployment build

# 2. 查看服务状态
make -C deployment ps

# 3. 查看日志
make -C deployment logs
```

### 方法二：直接使用 Docker Compose

```bash
# 进入部署目录
cd deployment

# 构建并启动所有服务
docker-compose up -d --build

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 分步部署

### 1. 启动中间件服务（可选，但推荐）

```bash
# 只启动中间件服务
make -C deployment up
```

### 2. 构建镜像

```bash
# 构建所有镜像
make -C deployment build-only
```

### 3. 启动所有服务

```bash
# 启动所有服务
make -C deployment up-all

# 或者构建并启动
make -C deployment build
```

### 4. 初始化数据库

```bash
# 在 Django 容器中执行迁移
make -C deployment django-migrate
```

## 本地开发部署

### 前端开发

```bash
# 启动中间件服务
make -C deployment up

# 启动 Django 后端（本地）
make -C deployment django

# 在新终端启动 React 前端（本地）
make -C deployment react
```

### 后端开发

```bash
# 启动中间件服务
make -C deployment up

# 启动 FastAPI（本地）
make -C deployment fastapi

# 启动 Celery Worker（本地）
make -C deployment celery
```

## 常用命令

### 查看服务

```bash
# 查看所有服务状态
make -C deployment ps

# 查看应用服务日志
make -C deployment logs-app

# 查看所有服务日志
make -C deployment logs
```

### 停止服务

```bash
# 停止所有服务
make -C deployment down

# 停止服务并删除数据
make -C deployment down-v
```

### 数据库操作

```bash
# Django 数据库迁移
make -C deployment django-migrate

# 进入 Django Shell
make -C deployment django-shell

# 初始化 NetOps Agent 数据库
make -C deployment init-db
```

## 访问服务

部署完成后，可以通过以下地址访问：

| 服务 | URL | 说明 |
|------|-----|------|
| React 前端 | http://localhost:3000 | 主界面 |
| FastAPI 文档 | http://localhost:8000/docs | API 文档 |
| Langfuse | http://localhost:3001 | 监控界面 |
| MinIO 管理 | http://localhost:9001 | 对象存储管理 |
| RabbitMQ 管理 | http://localhost:15672 | 消息队列管理 |

## 配置说明

### 环境变量

主要环境变量已在 `docker-compose.yml` 中配置，如需要修改，编辑该文件即可。

### 数据持久化

数据通过 Docker volumes 持久化，存储位置：
- PostgreSQL: `postgres-data` volume
- Redis: `redis-data` volume
- MinIO: `minio-data` volume
- RabbitMQ: `rabbitmq-data` volume

## 故障排查

### 查看服务状态

```bash
# 查看特定服务日志
docker-compose logs django
docker-compose logs fastapi
docker-compose logs react
```

### 重启服务

```bash
# 重启特定服务
docker-compose restart django

# 重启所有服务
docker-compose restart
```

### 重新构建服务

```bash
# 重新构建特定服务
docker-compose up -d --build django
```

## 生产部署建议

1. **环境变量配置
   - 修改所有默认密码
   - 设置 DEBUG=False
   - 配置 HTTPS

2. **性能调优
   - 根据需要调整资源限制
   - 配置日志轮转

3. **备份策略
   - 定期备份数据库
   - 备份 MinIO 数据

## 架构优势

与 Streamlit 相比，Django + React 架构优势：

- ✅ 更好的性能
- ✅ 更好的用户体验
- ✅ 可扩展性更强
- ✅ 前后端分离
- ✅ 更好的代码组织
- ✅ 更现代化技术栈
- ✅ 更好的可维护性
