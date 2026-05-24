# NetOps Multi-Agent System API 文档

## 目录
1. [概述](#概述)
2. [认证](#认证)
3. [API端点](#api端点)
4. [请求/响应示例](#请求响应示例)

---

## 概述

NetOps Multi-Agent System 提供RESTful API接口，支持：
- 智能问答 (Chat)
- 知识库检索 (RAG)
- ITSM Webhook集成
- 异步任务处理

### 基础信息

| 项目 | 值 |
|------|-----|
| 基础URL | `http://localhost:8000` |
| API版本 | v1 |
| 文档地址 | `http://localhost:8000/docs` |
| REST文档 | `http://localhost:8000/redoc` |

---

## 认证

当前版本暂不需要认证。生产环境部署时，请通过以下方式保护API：

1. **API Key认证**: 在请求头中添加 `X-API-Key`
2. **OAuth 2.0**: 集成企业SSO
3. **IP白名单**: 限制可访问的IP范围

---

## API端点

### 系统接口

#### 健康检查
```
GET /health
```

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-14T10:00:00Z",
  "services": {
    "postgres": true,
    "rag": true
  }
}
```

---

### Chat 接口

#### 发送消息
```
POST /api/v1/chat
```

**请求体**:
```json
{
  "query": "交换机端口Down了如何处理？",
  "thread_id": "可选的对话线程ID",
  "source": "chat",
  "metadata_filters": {}
}
```

**响应**:
```json
{
  "response": "根据您的问题，我建议按以下步骤处理...",
  "thread_id": "thread-abc123",
  "agent_type": "knowledge_qa",
  "references": [
    {
      "content": "...",
      "source": "交换机端口Down_SOP.md",
      "score": 0.95
    }
  ]
}
```

#### WebSocket实时对话
```
WS /ws/v1/chat
```

**发送消息**:
```json
{
  "query": "防火墙策略如何配置？",
  "thread_id": "可选的对话线程ID"
}
```

---

### RAG 接口

#### 知识检索
```
POST /api/v1/rag/search
```

**请求体**:
```json
{
  "query": "防火墙配置命令",
  "top_k": 6,
  "metadata_filters": {
    "category": "安全"
  }
}
```

**响应**:
```json
{
  "count": 6,
  "results": [
    {
      "content": "...",
      "source": "防火墙运维与排障_SOP.md",
      "score": 0.92
    }
  ]
}
```

---

### ITSM Webhook 接口

#### 防火墙策略生成
```
POST /api/v1/itsm/webhook/firewall-policy
```

**请求体**:
```json
{
  "ticket_id": "REQ202405140001",
  "ticket_title": "xx团队申请财务系统访问数据库防火墙策略开通",
  "service_catalog": "安全-防火墙策略开通",
  "requester": "zhang.san",
  "requester_dept": "财务部",
  "assignee": "li.si",
  "priority": "P2",
  "due_date": "2024-05-21",
  "policy_file": {
    "url": "https://itsm.company.com/attachments/policy_request_001.xlsx",
    "filename": "policy_request_001.xlsx",
    "md5": "a1b2c3d4e5f6..."
  },
  "topology_file": {
    "url": "https://config-center.company.com/topology/prod_topology.json",
    "filename": "topology.json"
  },
  "parameters": {
    "merge_enabled": true,
    "output_format": "huawei,h3c"
  },
  "callback_url": "https://itsm.company.com/api/change/create",
  "callback_headers": {
    "X-API-Key": "itsm_callback_key_123"
  }
}
```

**响应 (202 Accepted)**:
```json
{
  "task_id": "77297097-ab88-4c3a-a7e5-5475b95b7861",
  "celery_task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "ticket_id": "REQ202405140001",
  "status": "accepted",
  "message": "防火墙策略生成任务已提交，正在后台处理...",
  "query_endpoint": "/api/v1/tasks/6729e7d2-97ae-4d01-b069-caedb452de05"
}
```

#### 回调端点 (模拟ITSM接收)
```
POST /api/v1/itsm/webhook/callback
```

**接收到的回调数据**:
```json
{
  "version": "1.0",
  "timestamp": "2024-05-14T10:30:00+08:00",
  "callback_id": "cb_550e8400_e29b_41d4_a716_446655440000",
  "source_ticket_id": "REQ202405140001",
  "status": "success",
  "result": {
    "action": "update_ticket",
    "ticket_update": {
      "status": "配置已生成",
      "resolution_note": "策略配置文件已生成，下载后请按照变更流程执行",
      "attachments": [
        {
          "filename": "firewall_policies.zip",
          "download_url": "https://minio.company.com/bucket/path/file.zip"
        }
      ]
    }
  },
  "metadata": {
    "execution_time_ms": 12345
  }
}
```

---

### 任务接口

#### 查询任务状态
```
GET /api/v1/tasks/{task_id}
```

**响应 (进行中)**:
```json
{
  "task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "status": "processing",
  "celery_task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "result": "任务执行中..."
}
```

**响应 (成功)**:
```json
{
  "task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "status": "completed",
  "celery_task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "result": "任务执行成功",
  "file_url": "https://minio.company.com/bucket/path/file.zip"
}
```

**响应 (失败)**:
```json
{
  "task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "status": "failed",
  "celery_task_id": "6729e7d2-97ae-4d01-b069-caedb452de05",
  "error_message": "策略文件格式错误：第 15 行 IP 地址格式不正确"
}
```

---

## 请求/响应示例

### cURL 示例

#### Chat请求
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何查看交换机端口状态？",
    "thread_id": "session-001"
  }'
```

#### ITSM Webhook请求
```bash
curl -X POST http://localhost:8000/api/v1/itsm/webhook/firewall-policy \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "REQ001",
    "ticket_title": "测试防火墙策略",
    "service_catalog": "安全-防火墙策略开通",
    "requester": "test.user",
    "policy_file": {
      "url": "C:\\path\\to\\policies.xlsx",
      "filename": "policies.xlsx"
    },
    "callback_url": "http://localhost:8000/api/v1/itsm/webhook/callback"
  }'
```

### Python requests 示例

```python
import requests

# Chat请求
chat_response = requests.post(
    "http://localhost:8000/api/v1/chat",
    json={
        "query": "交换机端口Down了怎么办？",
        "thread_id": "test-thread"
    }
)
print(chat_response.json())

# ITSM Webhook请求
webhook_response = requests.post(
    "http://localhost:8000/api/v1/itsm/webhook/firewall-policy",
    json={
        "ticket_id": "REQ001",
        "ticket_title": "防火墙策略测试",
        "service_catalog": "安全-防火墙策略开通",
        "requester": "test.user",
        "policy_file": {
            "url": "C:\\path\\to\\policies.xlsx",
            "filename": "policies.xlsx"
        },
        "callback_url": "http://localhost:8000/api/v1/itsm/webhook/callback"
    }
)
print(webhook_response.json())
task_id = webhook_response.json()["celery_task_id"]

# 查询任务状态
import time
for _ in range(10):
    status_response = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}")
    status = status_response.json()
    print(f"状态: {status['status']}")
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(2)
```

---

## 错误代码

| 错误码 | 描述 | 可能原因 |
|--------|------|----------|
| POLICY_GEN_001 | 策略生成失败 | 策略文件格式错误 |
| POLICY_GEN_002 | 拓扑文件错误 | 拓扑JSON格式不正确 |
| POLICY_GEN_003 | 网络连接失败 | 无法下载策略文件 |
| NETWORK_ERROR | 网络错误 | 请求超时或连接失败 |
| VALIDATION_ERROR | 参数验证错误 | 请求参数不符合规范 |

---

## 限流说明

当前版本未实现限流。生产环境建议：

- Chat接口: 100请求/分钟/用户
- RAG接口: 60请求/分钟/用户
- Webhook接口: 200请求/分钟/IP

---

## Webhook 安全

### 验证签名

ITSM发送Webhook时，应验证请求签名：

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### IP白名单

在生产环境中，配置ITSM服务器的IP白名单：
- 配置Web服务器只允许ITSM IP访问 `/api/v1/itsm/*` 路径
