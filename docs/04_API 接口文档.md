# 04 API 接口文档

> 版本：2026-05-24  
> **对外入口：** Django BFF `http://localhost:8001/api/`  
> **内部网关：** FastAPI `http://localhost:8000`（生产 Docker 中通常不映射宿主机）

OpenAPI 交互文档：`http://localhost:8000/docs`

---

## 1. 认证

### 1.1 JWT 登录（BFF）

```http
POST /api/auth/login/
Content-Type: application/json

{"username": "admin", "password": "admin123"}
```

**响应：**

```json
{
  "access": "<jwt_access>",
  "refresh": "<jwt_refresh>",
  "user": {"id": 1, "username": "admin", "role": "admin"}
}
```

### 1.2 后续请求

```http
Authorization: Bearer <jwt_access>
```

BFF 代理 FastAPI 时透传 `Authorization`，并注入可信头：

- `X-Forwarded-From: django-bff`
- `X-Internal-Request: true`
- `X-Request-Id: <uuid>`（BFF 中间件生成）

### 1.3 其他认证端点（BFF）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/refresh/` | 刷新 token |
| POST | `/api/auth/logout/` | 登出 |
| GET | `/api/auth/me/` | 当前用户 |
| POST | `/api/auth/change-password/` | 修改密码 |
| GET/POST | `/api/auth/users/` | 用户列表/创建（admin） |
| GET/PUT/DELETE | `/api/auth/users/{id}/` | 用户详情 |
| POST | `/api/auth/users/{id}/reset-password/` | 重置密码 |

### 1.4 FastAPI 直连限制

`ENFORCE_BFF_ORIGIN=true` 时，非 BFF 来源请求返回：

```json
{
  "success": false,
  "error": {"code": "bff_origin_required", "message": "..."},
  "request_id": "..."
}
```

---

## 2. 统一响应约定

### 2.1 成功

多数接口返回业务 JSON；聊天接口含 `response`、`thread_id`、`agent_type` 等。

### 2.2 错误信封（P2）

```json
{
  "success": false,
  "error": {
    "code": "skill_not_found",
    "message": "Skill xxx 不存在",
    "details": {}
  },
  "request_id": "req-abc123"
}
```

错误码详见 [09_错误码定义文档](./09_错误码定义文档.md)。

---

## 3. 系统与健康

| BFF 路径 | FastAPI 路径 | 方法 | 说明 |
|----------|--------------|------|------|
| `/api/health/` | `/health` | GET | 健康检查 |
| `/api/health/diagnostics/` | `/health/diagnostics` | GET | 诊断（PG/Redis/RAG 等） |
| `/api/gateway/` | `/` | GET | 网关信息 |

**健康检查响应示例：**

```json
{
  "status": "healthy",
  "services": {"postgres": true, "rag": true}
}
```

---

## 4. 聊天

| BFF 路径 | FastAPI 路径 | 方法 | 说明 |
|----------|--------------|------|------|
| `/api/chat/` | `/api/v1/chat` | POST | 同步聊天 |
| `/api/chat/stream/` | `/api/v1/chat/stream` | POST | SSE 流式聊天 |
| `/api/chat/upload/` | `/api/v1/chat/upload` | POST | 上传附件 |
| `ws://host/ws/v1/chat` | `/ws/v1/chat` | WebSocket | 实时对话 |

### 4.1 同步聊天

**请求：**

```json
{
  "query": "生成防火墙策略，工单号 rg001",
  "thread_id": "可选",
  "conversation_id": "可选",
  "source": "chat",
  "ticket_id": "rg001",
  "metadata_filters": {}
}
```

**响应：**

```json
{
  "response": "...",
  "thread_id": "thread-abc",
  "agent_type": "workflow_starter",
  "references": [],
  "trace_id": "lf-xxx"
}
```

### 4.2 SSE 流式聊天

**请求：** 同同步聊天

**SSE 事件类型：**

| event | 说明 |
|-------|------|
| `trace_start` | trace_id、langfuse_url（admin） |
| `status` | 运行状态 |
| `node_start` | LangGraph 节点开始（admin/operator） |
| `trace_update` | 进度摘要 |
| `final_answer` | 最终回答 + trace_id |
| `error` | 错误信息 |

### 4.3 任务状态

| BFF | FastAPI | 方法 |
|-----|---------|------|
| `/api/tasks/{task_id}/` | `/api/v1/tasks/{task_id}` | GET |

---

## 5. 对话 CRUD

| BFF 路径 | FastAPI 路径 | 方法 |
|----------|--------------|------|
| `/api/conversations/` | `/api/v1/conversations` | GET, POST |
| `/api/conversations/{id}/` | `/api/v1/conversations/{id}` | GET, PUT, DELETE |
| `/api/conversations/{id}/messages/` | `/api/v1/conversations/{id}/messages` | POST |
| `/api/conversations/{id}/summarize/` | `/api/v1/conversations/{id}/summarize` | POST |

---

## 6. RAG

| BFF | FastAPI | 方法 |
|-----|---------|------|
| `/api/rag/search/` | `/api/v1/rag/search` | POST |

**请求：**

```json
{
  "query": "防火墙配置命令",
  "top_k": 6,
  "metadata_filters": {"category": "安全"}
}
```

---

## 7. ITSM Webhook

| BFF | FastAPI | 方法 |
|-----|---------|------|
| `/api/itsm/webhook/` | `/api/v1/itsm/webhook` | POST |
| `/api/itsm/webhook/callback/` | `/api/v1/itsm/webhook/callback` | POST |
| `/api/itsm/webhook/firewall-policy/` | `/api/v1/itsm/webhook/firewall-policy` | POST |

动态路由：`POST /api/v1/itsm/webhook/{route_key}`

---

## 8. Skill 管理

前缀：`/api/skills/` → FastAPI `/api/v1/skills`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表 |
| GET | `/stats/` | 统计 |
| POST | `/` | 创建 |
| GET/PUT/DELETE | `/{skill_name}/` | 详情/更新/删除 |
| GET/PUT | `/{skill_name}/content/` | SKILL.md 内容 |
| GET/POST | `/{skill_name}/files/` | 附属文件 |
| PATCH | `/{skill_name}/toggle/` | 启用/禁用 |
| POST | `/{skill_name}/reload/` | 热加载 |
| POST | `/{skill_name}/test-run/` | 测试执行 |
| GET | `/{skill_name}/schema/` | 输入 schema |
| POST | `/reload-all/` | 全量重载 |

---

## 9. 知识库

前缀：`/api/knowledge/` → FastAPI `/api/v1/knowledge`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/documents/` | 列表/上传 |
| GET | `/documents/{path}/content/` | 文档内容 |
| DELETE | `/documents/{path}/` | 删除 |
| GET | `/stats/` | 统计 |
| POST | `/reindex/` | 重建索引 |

---

## 10. Workflow

前缀：`/api/workflows/` → FastAPI `/api/v1/workflows`

### 10.1 模板与插件

| 方法 | BFF 路径 | 说明 |
|------|----------|------|
| GET | `/templates/` | 模板列表 |
| GET | `/templates/{name}/` | 模板详情 |
| GET | `/templates/{name}/dsl/` | DSL 源码 |
| GET | `/plugins/` | 插件列表 |
| POST | `/import/` | 导入插件 |
| POST | `/validate/` | 校验 YAML |
| POST | `/preview/` | 预览 |
| POST | `/generate/` | AI 生成 Workflow |
| POST | `/reload/` | 重载注册表 |
| POST | `/plugins/{name}/publish/` | 发布 |
| GET | `/market/templates/` | 模板市场 |

### 10.2 运行与监控

| 方法 | BFF 路径 | 说明 |
|------|----------|------|
| GET | `/runs/` | 运行列表 |
| POST | `/runs/test/` | 测试运行 |
| GET | `/{run_id}/` | 运行详情 |
| GET | `/{run_id}/timeline/` | 时间线 |
| GET | `/{run_id}/events/stream/` | SSE 进度流 |

**运行详情含：** `status`、`context`、`langfuse_url`（如已配置 Langfuse）

---

## 11. 通知

前缀：`/api/notifications/` → FastAPI `/api/v1/notifications`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表 |
| POST | `/clear/` | 清空 |
| POST | `/{id}/read/` | 标记已读 |

---

## 12. 网盘（Storage）

前缀：`/api/storage/` → FastAPI `/api/v1/storage`

| 分组 | 主要路径 |
|------|----------|
| 健康 | `/health/` |
| 团队 | `/teams/`、`/teams/{id}/members/` |
| 目录 | `/folders/`、`/folders/tree/`、`/folders/{id}/move/` |
| 文件 | `/list/`、`/upload/init/`、`/upload/complete/`、`/files/{id}/download/` |
| 分享 | `/share/`、`/share/folder/` |

---

## 13. BFF 与 FastAPI 路径映射规则

1. 浏览器/前端统一访问 **`http://localhost:8001/api/...`**
2. BFF view 将路径映射为 FastAPI `/api/v1/...`（见 `web/django_backend/bff/views/`）
3. 生产环境 React Nginx 将 `/api/`、`/ws/` 代理至 Django（`deployment/nginx.conf`）

---

## 14. 演示账号

| 用户 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | admin |
| operator | operator123 | operator |
| viewer | viewer123 | viewer |

---

## 15. 相关文档

- 认证细节：[auth-rbac-plan.md](./auth-rbac-plan.md)
- SSE / Langfuse：[langfuse-sse-plan.md](./langfuse-sse-plan.md)
- 错误码：[09_错误码定义文档](./09_错误码定义文档.md)
