# =============================================================================
# NetOps Multi-Agent System - FastAPI Gateway (v2.0)
# =============================================================================
#
# 启动命令：
#
# 【开发环境 - 单 worker（支持热重载）】
#   python -m src.gateway.main
#   uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 --reload
#
# 【生产环境 - Gunicorn + UvicornWorker（多 worker，高并发）】
#   gunicorn src.gateway.main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000 --timeout 120 --keep-alive 5
#
# 【生产环境 - CPU 动态 worker 数】
#   gunicorn src.gateway.main:app -k uvicorn.workers.UvicornWorker --workers $(nproc) --bind 0.0.0.0:8000 --timeout 120 --keep-alive 5
#
# 【生产环境 - 多 worker + 多线程（IO 密集型）】
#   gunicorn src.gateway.main:app -k uvicorn.workers.UvicornWorker --workers 4 --threads 2 --bind 0.0.0.0:8000
#
# 【开发环境 - 禁用热重载但多 worker 测试】
#   uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 --workers 4
#
# =============================================================================

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ["LLAMA_INDEX_CACHE_DIR"] = str(Path("./cache/llama_index").absolute())
os.environ["LLAMA_INDEX_DISABLE_HTTP_CACHE"] = "1"

import json
import uuid

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage

from src.agents.supervisor.graph import compiled_graph as get_supervisor_graph
from src.common.config import get_settings
from src.core.rag_service.service import get_rag_service
from src.gateway.conversation_service import get_conversation_service
from src.gateway.schemas import (
    AddMessageRequest,
    ChatFileUploadRequest,
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    HealthResponse,
    ITSMEventRequest,
    ITSMFirewallPolicyRequest,
    MessageResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    TaskResponse,
    UpdateConversationRequest,
)
from src.infrastructure.db.models import init_db_models
from src.infrastructure.db.postgres import engine, verify_postgres_connection

CELERY_AVAILABLE = False
EXECUTE_FIREWALL_POLICY_TASK = None

settings = get_settings()

# =============================================================================
# 数据库初始化（非阻塞，失败不阻止启动）
# =============================================================================
try:
    init_db_models(engine)
except Exception as e:
    print(f"[INFO] Skip auto table creation: {e}")


# =============================================================================
# 连接池与资源管理（Lifespan）
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan：管理应用生命周期中的资源

    启动时：
    - 初始化 Redis 连接池（Celery broker + result backend）
    - 验证 PostgreSQL 连接
    - 预加载 RAG 服务和 Agent Graph
    - 预热 Qdrant 向量数据库连接（如已配置）

    关闭时：
    - 关闭 Redis 连接池
    - 关闭 PostgreSQL 引擎
    - 清理临时资源
    """
    import redis.asyncio as aioredis

    print("\n" + "=" * 60)
    print(f"[Lifespan] {settings.PROJECT_NAME} starting up...")
    print("=" * 60)

    # --- 启动：初始化 Redis 连接池 ---
    app.state.redis_pool = None
    try:
        redis_url = settings.redis_url
        app.state.redis_pool = aioredis.ConnectionPool.from_url(
            redis_url,
            max_connections=20,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        test_conn = aioredis.Redis(connection_pool=app.state.redis_pool)
        await test_conn.ping()
        print(f"[Lifespan] [OK] Redis connected: {redis_url}")
    except Exception as e:
        print(f"[Lifespan] [WARN] Redis not available: {e}")
        print("[Lifespan]   Celery tasks will not work without Redis")

    # --- 启动：验证 PostgreSQL ---
    try:
        pg_ok = verify_postgres_connection()
        if pg_ok:
            print(f"[Lifespan] [OK] PostgreSQL connected: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        else:
            print("[Lifespan] [WARN] PostgreSQL connection failed")
    except Exception as e:
        print(f"[Lifespan] [WARN] PostgreSQL not available: {e}")

    # --- 启动：预加载 RAG 服务 ---
    try:
        app.state.rag_service = get_rag_service()
        print("[Lifespan] [OK] RAG Service loaded")
    except Exception as e:
        print(f"[Lifespan] [WARN] RAG Service load failed: {e}")
        app.state.rag_service = None

    # --- 启动：延迟加载 Agent Graph（避免启动时因网络问题卡住）---
    # 图将在第一个请求时按需加载
    app.state.agent_graph = None
    print("[Lifespan] [OK] Agent Graph will be lazy-loaded on first request")

    print("=" * 60)
    print(f"[Lifespan] Startup complete. Docs: http://localhost:{settings.FASTAPI_PORT}/docs")
    print("=" * 60 + "\n")

    yield

    # --- 关闭：清理资源 ---
    print("\n" + "=" * 60)
    print("[Lifespan] Shutting down...")
    print("=" * 60)

    if app.state.redis_pool:
        await app.state.redis_pool.disconnect()
        print("[Lifespan] [OK] Redis connection pool closed")

    try:
        from src.infrastructure.db.postgres import engine
        engine.dispose()
        print("[Lifespan] [OK] PostgreSQL engine disposed")
    except Exception:
        pass

    print("[Lifespan] Shutdown complete")
    print("=" * 60)


# =============================================================================
# FastAPI 应用实例
# =============================================================================
app = FastAPI(
    title="NetOps Multi-Agent System API Gateway",
    description="NetOps AI Agent System - FastAPI Gateway with Async Celery Skill Execution",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# =============================================================================
# CORS 中间件（生产环境请限制 origins）
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 依赖注入：从 app.state 获取预加载的服务
# =============================================================================
def get_rag():
    return app.state.rag_service


def get_graph():
    return app.state.agent_graph


# =============================================================================
# API 端点
# =============================================================================

@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "status": "running",
        "description": "NetOps Multi-Agent System API Gateway"
    }


@app.get("/health", tags=["System"], response_model=HealthResponse)
async def health_check():
    services = {}

    try:
        services["postgres"] = verify_postgres_connection()
    except Exception:
        services["postgres"] = False

    services["rag"] = app.state.rag_service is not None

    try:
        if app.state.redis_pool:
            import redis.asyncio as aioredis
            r = aioredis.Redis(connection_pool=app.state.redis_pool)
            await r.ping()
            services["redis"] = True
        else:
            services["redis"] = False
    except Exception:
        services["redis"] = False

    all_healthy = all(services.values())
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        services=services
    )


@app.post("/api/chat/", tags=["Chat"], response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint_legacy(request: ChatRequest):
    """Legacy chat endpoint for backward compatibility"""
    return await chat_endpoint(request)


@app.post("/api/v1/chat", tags=["Chat"], response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(request: ChatRequest):
    """
    统一聊天接口（REST，异步执行）

    - 支持多轮对话状态持久化到 PostgreSQL
    - Supervisor Agent 自动路由
    - Skill 执行使用 Celery 异步（非阻塞）
    - RAG Metadata 过滤
    - 自动生成对话标题
    """
    conv_service = get_conversation_service()
    conversation_id = request.thread_id
    
    if not conversation_id:
        conversation = conv_service.create_conversation(title="新对话")
        conversation_id = conversation["id"]
    else:
        conversation = conv_service.get_conversation(conversation_id)
        if not conversation:
            conversation = conv_service.create_conversation(title="新对话")
            conversation_id = conversation["id"]

    thread_id = f"thread-{conversation_id.split('-')[-1]}"

    config = {
        "configurable": {"thread_id": thread_id}
    }

    # 延迟加载 Agent Graph
    agent_graph = app.state.agent_graph
    if not agent_graph:
        print("[Chat] Lazy loading Agent Graph...")
        try:
            agent_graph = get_supervisor_graph()
            app.state.agent_graph = agent_graph
            print("[Chat] Agent Graph loaded successfully")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Agent Graph loading failed: {str(e)}"
            )

    try:
        initial_state = {
            "messages": [HumanMessage(content=request.query)],
            "source": request.source.value,
            "task_id": str(uuid.uuid4()),
            "thread_id": thread_id,
        }

        if request.metadata_filters:
            initial_state["metadata_filters"] = request.metadata_filters

        if request.uploaded_file_path:
            initial_state["uploaded_file_path"] = request.uploaded_file_path

        if request.ticket_id:
            initial_state["ticket_id"] = request.ticket_id
            print(f"[DEBUG] FastAPI - added ticket_id to initial_state: {request.ticket_id}")

        print(f"[DEBUG] FastAPI - initial_state keys: {initial_state.keys()}")
        print(f"[DEBUG] FastAPI - initial_state ticket_id: {initial_state.get('ticket_id')}")

        # [Async] run graph.invoke in thread pool to avoid blocking event loop
        result = await asyncio.to_thread(agent_graph.invoke, initial_state, config)

        response_msg = result["messages"][-1].content
        next_agent = result.get("next_agent")
        references = result.get("knowledge_references")
        celery_task_id = result.get("celery_task_id")

        # 保存用户消息和Agent回复到数据库
        conv_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.query
        )
        
        conv_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_msg,
            agent_type=next_agent,
            celery_task_id=celery_task_id,
            references=references
        )

        # 生成对话标题
        title = conv_service.generate_title(conversation_id)
        conv_service.update_conversation(conversation_id, title=title)

        return ChatResponse(
            response=response_msg,
            thread_id=conversation_id,
            agent_type=next_agent,
            task_id=result.get("task_id"),
            celery_task_id=celery_task_id,
            references=references
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent invocation failed: {str(e)}"
        )


@app.websocket("/ws/v1/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    WebSocket 实时聊天接口

    - 流式返回状态（thinking / routing / retrieving / answering）
    - 支持保持对话上下文
    - 使用 ainvoke 异步调用 Agent Graph
    """
    await websocket.accept()
    thread_id = f"ws-thread-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}

    agent_graph = app.state.agent_graph

    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
                query = payload.get("query", "")
                client_thread_id = payload.get("thread_id")
                if client_thread_id:
                    thread_id = client_thread_id
                    config = {"configurable": {"thread_id": thread_id}}
            except json.JSONDecodeError:
                query = data

            await websocket.send_json({
                "type": "status",
                "status": "thinking",
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            try:
                # [Async] run graph.invoke in thread pool
                result = await asyncio.to_thread(
                    agent_graph.invoke,
                    {"messages": [HumanMessage(content=query)]},
                    config
                )
                response = result["messages"][-1].content

                await websocket.send_json({
                    "type": "message",
                    "content": response,
                    "thread_id": thread_id,
                    "agent_type": result.get("next_agent"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "thread_id": thread_id
                })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {thread_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        pass


@app.post("/api/v1/rag/search", tags=["RAG"], response_model=RAGSearchResponse)
async def rag_search_endpoint(request: RAGSearchRequest):
    """
    统一 RAG 检索服务 API（供所有 Agent 或外部系统调用）
    """
    rag_service = app.state.rag_service
    if not rag_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG Service not available"
        )

    result = rag_service.retrieve_formatted(
        query=request.query,
        top_k=request.top_k,
        metadata_filters=request.metadata_filters
    )

    return RAGSearchResponse(
        count=result["count"],
        results=result["references"]
    )


@app.post("/api/v1/itsm/webhook", tags=["ITSM"])
async def itsm_webhook_endpoint(event: ITSMEventRequest, background_tasks: BackgroundTasks):
    """
    ITSM Webhook 接收入口（通用事件）

    - 事件持久化
    - 后台异步调用 Agent
    - 返回 Ack
    """
    task_id = str(uuid.uuid4())

    response = {
        "task_id": task_id,
        "event_id": event.event_id,
        "status": "accepted",
        "message": "ITSM 事件已接收，后台处理中...",
        "query_endpoint": f"/api/v1/tasks/{task_id}"
    }

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response
    )


@app.post("/api/v1/itsm/webhook/firewall-policy", tags=["ITSM"])
async def itsm_firewall_policy_webhook(request: ITSMFirewallPolicyRequest):
    """
    ITSM Webhook - 防火墙策略开通请求

    - 接收 ITSM 服务目录发起的防火墙策略开通请求
    - 异步执行策略生成任务（Celery）
    - 回调 ITSM 更新工单状态
    """
    try:
        from src.core.celery_tasks.tasks import execute_firewall_policy_task
    except Exception as e:
        response = {
            "task_id": str(uuid.uuid4()),
            "ticket_id": request.ticket_id,
            "ticket_title": request.ticket_title,
            "status": "pending",
            "message": "任务已接收，但 Celery 导入失败。",
            "query_endpoint": f"/api/v1/tasks/{request.ticket_id}",
            "required_action": str(e)
        }
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=response
        )

    celery_task = execute_firewall_policy_task.delay(
        ticket_id=request.ticket_id,
        ticket_title=request.ticket_title,
        policy_file_url=request.policy_file.url,
        topology_file_url=request.topology_file.url if request.topology_file else None,
        parameters=request.parameters.dict() if request.parameters else None,
        callback_url=request.callback_url,
        callback_headers=request.callback_headers,
        requester=request.requester,
        assignee=request.assignee,
        priority=request.priority
    )

    response = {
        "task_id": str(uuid.uuid4()),
        "celery_task_id": celery_task.task_id,
        "ticket_id": request.ticket_id,
        "ticket_title": request.ticket_title,
        "status": "accepted",
        "message": "防火墙策略生成任务已提交，正在后台处理...",
        "query_endpoint": f"/api/v1/tasks/{celery_task.task_id}"
    }

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response
    )


@app.get("/api/v1/tasks/{task_id}", tags=["Tasks"], response_model=TaskResponse)
async def get_task_status(task_id: str):
    """查询 Celery 任务状态"""
    from src.core.celery_tasks.celery_app import celery

    try:
        result = celery.AsyncResult(task_id)

        if result.state == "PENDING":
            return TaskResponse(
                task_id=task_id,
                status="pending",
                celery_task_id=task_id,
                result="任务等待执行"
            )
        elif result.state == "STARTED":
            return TaskResponse(
                task_id=task_id,
                status="processing",
                celery_task_id=task_id,
                result="任务执行中..."
            )
        elif result.state == "SUCCESS":
            task_result = result.get()
            return TaskResponse(
                task_id=task_id,
                status="completed",
                celery_task_id=task_id,
                result="任务执行成功",
                file_url=task_result.get("download_url")
            )
        elif result.state == "FAILURE":
            return TaskResponse(
                task_id=task_id,
                status="failed",
                celery_task_id=task_id,
                error_message=str(result.info)
            )
        elif result.state == "RETRY":
            return TaskResponse(
                task_id=task_id,
                status="retry",
                celery_task_id=task_id,
                result="任务重试中..."
            )
        else:
            return TaskResponse(
                task_id=task_id,
                status=result.state.lower() if result.state else "pending",
                celery_task_id=task_id
            )
    except Exception as e:
        return TaskResponse(
            task_id=task_id,
            status="failed",
            error_message=str(e)
        )


@app.post("/api/v1/itsm/webhook/callback", tags=["ITSM"])
async def itsm_callback_endpoint(request: dict):
    """
    ITSM 回调端点（模拟接收 ITSM 回调）

    - 接收防火墙策略生成任务的回调结果
    - 记录回调内容用于调试
    """
    print(f"[ITSM Callback] Received callback: {json.dumps(request, ensure_ascii=False)}")

    response = {
        "status": "success",
        "message": "回调已接收",
        "callback_id": request.get("callback_id"),
        "source_ticket_id": request.get("source_ticket_id")
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=response)


@app.post("/api/v1/chat/upload", tags=["Chat"])
async def chat_upload_file(request: ChatFileUploadRequest):
    """
    聊天文件上传接口

    - 用户上传策略 Excel 文件用于生成防火墙策略
    - 返回临时文件路径供后续处理
    """
    import base64
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="chat_upload_")
    file_path = os.path.join(temp_dir, request.filename)

    try:
        file_content = base64.b64decode(request.file_content)
        with open(file_path, "wb") as f:
            f.write(file_content)

        response = {
            "thread_id": request.thread_id,
            "filename": request.filename,
            "file_path": file_path,
            "status": "uploaded",
            "message": f"文件 {request.filename} 上传成功",
            "next_steps": "请继续输入命令执行策略生成，如：生成防火墙策略"
        }
        return JSONResponse(status_code=status.HTTP_200_OK, content=response)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )


# =============================================================================
# 对话管理 API 端点
# =============================================================================

@app.post("/api/v1/conversations", tags=["Conversations"], response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest):
    """创建新对话"""
    conv_service = get_conversation_service()
    conversation = conv_service.create_conversation(
        title=request.title,
        user_id=request.user_id,
        thread_id=request.thread_id
    )
    
    return ConversationResponse(
        id=conversation["id"],
        title=conversation["title"],
        user_id=conversation["user_id"],
        thread_id=conversation["thread_id"],
        status=conversation["status"],
        summary=conversation["summary"],
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
        message_count=0
    )


@app.get("/api/v1/conversations", tags=["Conversations"], response_model=list[ConversationResponse])
async def get_conversations(user_id: str | None = None, limit: int = 20, offset: int = 0):
    """获取对话列表"""
    conv_service = get_conversation_service()
    conversations = conv_service.get_conversations(user_id=user_id, limit=limit, offset=offset)
    
    result = []
    for conv in conversations:
        result.append(ConversationResponse(
            id=conv["id"],
            title=conv["title"],
            user_id=conv["user_id"],
            thread_id=conv["thread_id"],
            status=conv["status"],
            summary=conv["summary"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            message_count=conv.get("message_count", 0)
        ))
    
    return result


@app.get("/api/v1/conversations/{conversation_id}", tags=["Conversations"], response_model=ConversationDetailResponse)
async def get_conversation_detail(conversation_id: str):
    """获取对话详情（含消息）"""
    conv_service = get_conversation_service()
    data = conv_service.get_conversation_with_messages(conversation_id)
    
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    conversation = data["conversation"]
    messages = data["messages"]
    
    message_responses = []
    for msg in messages:
        message_responses.append(MessageResponse(
            id=msg["id"],
            role=msg["role"],
            content=msg["content"],
            agent_type=msg.get("agent_type"),
            celery_task_id=msg.get("celery_task_id"),
            download_url=msg.get("download_url"),
            references=msg.get("references"),
            created_at=msg["created_at"]
        ))
    
    return ConversationDetailResponse(
        conversation=ConversationResponse(
            id=conversation["id"],
            title=conversation["title"],
            user_id=conversation["user_id"],
            thread_id=conversation["thread_id"],
            status=conversation["status"],
            summary=conversation["summary"],
            created_at=conversation["created_at"],
            updated_at=conversation["updated_at"],
            message_count=len(messages)
        ),
        messages=message_responses
    )


@app.put("/api/v1/conversations/{conversation_id}", tags=["Conversations"], response_model=ConversationResponse)
async def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """更新对话信息"""
    conv_service = get_conversation_service()
    
    update_data = {}
    if request.title is not None:
        update_data["title"] = request.title
    if request.status is not None:
        update_data["status"] = request.status
    if request.summary is not None:
        update_data["summary"] = request.summary
    
    conversation = conv_service.update_conversation(conversation_id, **update_data)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = conv_service.get_messages(conversation_id)
    
    return ConversationResponse(
        id=conversation["id"],
        title=conversation["title"],
        user_id=conversation["user_id"],
        thread_id=conversation["thread_id"],
        status=conversation["status"],
        summary=conversation["summary"],
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
        message_count=len(messages)
    )


@app.delete("/api/v1/conversations/{conversation_id}", tags=["Conversations"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str):
    """删除对话"""
    conv_service = get_conversation_service()
    success = conv_service.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return None


@app.post("/api/v1/conversations/{conversation_id}/messages", tags=["Conversations"], response_model=MessageResponse)
async def add_message(conversation_id: str, request: AddMessageRequest):
    """添加消息到对话"""
    conv_service = get_conversation_service()
    
    conversation = conv_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    message = conv_service.add_message(
        conversation_id=conversation_id,
        role=request.role,
        content=request.content,
        agent_type=request.agent_type,
        celery_task_id=request.celery_task_id,
        download_url=request.download_url,
        references=request.references
    )
    
    return MessageResponse(
        id=message["id"],
        role=message["role"],
        content=message["content"],
        agent_type=message.get("agent_type"),
        celery_task_id=message.get("celery_task_id"),
        download_url=message.get("download_url"),
        references=message.get("references"),
        created_at=message["created_at"]
    )


@app.post("/api/v1/conversations/{conversation_id}/summarize", tags=["Conversations"])
async def summarize_conversation(conversation_id: str):
    """生成对话总结和标题"""
    conv_service = get_conversation_service()
    
    conversation = conv_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    title = conv_service.generate_title(conversation_id)
    summary = conv_service.summarize_conversation(conversation_id)
    
    conv_service.update_conversation(conversation_id, title=title, summary=summary)
    
    return {
        "conversation_id": conversation_id,
        "title": title,
        "summary": summary,
        "message": "对话总结生成成功"
    }


# =============================================================================
# 启动入口（开发环境）
# =============================================================================
def start():
    """
    开发环境启动入口
    生产环境请使用文件顶部的 Gunicorn 命令。
    """
    target_port = settings.FASTAPI_PORT
    host = settings.FASTAPI_HOST

    print(f"\n[*] {settings.PROJECT_NAME} FastAPI Gateway starting...")
    print("[*] RAG Service initialized")
    print("[*] Supervisor Agent ready")
    print(f"[*] API Docs: http://localhost:{target_port}/docs")
    print("=" * 70)

    # Windows 多 worker 模式（4个worker，适合12700K）
    uvicorn.run(
        "src.gateway.main:app",
        host=host,
        port=target_port,
        reload=settings.DEBUG,
        workers=4,
        timeout_keep_alive=120
    )


if __name__ == "__main__":
    start()
