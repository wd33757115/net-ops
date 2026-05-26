from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    CHAT = "chat"
    ITSM_WEBHOOK = "itsm_webhook"


class AgentType(str, Enum):
    KNOWLEDGE_QA = "knowledge_qa"
    SCRIPT_EXECUTOR = "script_executor"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


class ChatRequest(BaseModel):
    query: str = Field(..., description="用户查询", examples=["交换机端口Down了如何处理？"])
    thread_id: str | None = Field(None, description="对话线程ID（用于多轮持久化）")
    user_id: str | None = Field(None, description="用户ID")
    source: SourceType = Field(default=SourceType.CHAT)
    metadata_filters: dict[str, Any] | None = Field(None, description="RAG元数据过滤条件")
    uploaded_file_path: str | None = Field(None, description="已上传的文件路径（用于策略生成等场景）")
    ticket_id: str | None = Field(None, description="工单编号（可选，用于防火墙策略生成等场景，格式如REQ2025051800001）")
    async_mode: bool = Field(default=True, description="是否异步执行耗时任务（返回 celery_task_id 后由客户端轮询 /api/v1/tasks/{task_id}）")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent返回内容")
    thread_id: str = Field(..., description="对话线程ID（用于续谈）")
    agent_type: str | None = Field(None, description="实际处理的Agent类型")
    task_id: str | None = Field(None)
    celery_task_id: str | None = Field(None, description="Celery任务ID（用于轮询查询异步任务状态）")
    download_url: str | None = Field(None, description="直接下载链接（同步执行完成时返回）")
    references: list[dict] | None = Field(None, description="知识库引用文档")


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    celery_task_id: str | None = None
    result: str | None = None
    file_url: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ITSMEventRequest(BaseModel):
    event_id: str = Field(..., description="ITSM事件唯一ID")
    event_type: str = Field(default="incident")
    source_system: str = Field(default="ITSM")
    title: str = Field(..., description="事件标题")
    description: str | None = Field(None, description="事件详情")
    priority: str = Field(default="medium")
    callback_url: str | None = Field(None, description="结果回调URL")
    raw_payload: dict[str, Any] | None = None


class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=6, ge=1, le=20)
    metadata_filters: dict[str, Any] | None = None


class RAGSearchResponse(BaseModel):
    count: int
    results: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    services: dict[str, bool] = Field(default_factory=dict)


class PolicyFile(BaseModel):
    url: str = Field(..., description="策略文件下载地址")
    filename: str = Field(..., description="文件名")
    md5: str | None = Field(None, description="文件MD5校验值")


class TopologyFile(BaseModel):
    url: str = Field(..., description="拓扑文件下载地址")
    filename: str = Field(..., description="文件名")


class PolicyParameters(BaseModel):
    merge_enabled: bool = Field(default=True, description="是否启用合并")
    output_format: str = Field(default="huawei,h3c", description="输出格式")


class ITSMFirewallPolicyRequest(BaseModel):
    ticket_id: str = Field(..., description="ITSM服务请求单号")
    ticket_title: str = Field(..., description="请求标题")
    service_catalog: str = Field(..., description="服务目录")
    requester: str = Field(..., description="请求人")
    requester_dept: str | None = Field(None, description="请求人部门")
    assignee: str | None = Field(None, description="指派的执行人")
    priority: str = Field(default="P2", description="优先级")
    due_date: str | None = Field(None, description="截止日期")
    policy_file: PolicyFile = Field(..., description="策略Excel文件信息")
    topology_file: TopologyFile | None = Field(None, description="拓扑文件")
    parameters: PolicyParameters | None = Field(None, description="额外参数")
    callback_url: str = Field(..., description="回调地址")
    callback_headers: dict[str, str] | None = Field(None, description="回调请求头")


class ITSMCallbackAttachment(BaseModel):
    filename: str = Field(..., description="附件文件名")
    download_url: str = Field(..., description="附件下载URL")


class ITSMTicketUpdate(BaseModel):
    status: str = Field(..., description="工单状态")
    resolution_note: str | None = Field(None, description="解决备注")
    attachments: list[ITSMCallbackAttachment] | None = Field(None, description="附件列表")


class ITSMCallbackResult(BaseModel):
    action: str = Field(..., description="动作类型")
    ticket_update: ITSMTicketUpdate | None = Field(None, description="工单更新内容")


class ITSMCallbackError(BaseModel):
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    details: dict[str, Any] | None = Field(None, description="详细错误信息")
    suggested_action: str | None = Field(None, description="建议的解决措施")


class ITSMCallbackResponse(BaseModel):
    version: str = Field(default="1.0", description="回调协议版本")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    callback_id: str = Field(..., description="回调唯一标识")
    source_ticket_id: str = Field(..., description="源工单号")
    status: str = Field(..., description="状态: success/failed/partial")
    result: ITSMCallbackResult | None = Field(None, description="成功结果")
    error: ITSMCallbackError | None = Field(None, description="错误信息")
    metadata: dict[str, Any] | None = Field(None, description="元数据")


class ChatFileUploadRequest(BaseModel):
    thread_id: str = Field(..., description="对话线程ID")
    user_id: str | None = Field(None, description="用户ID")
    filename: str = Field(..., description="文件名")
    file_content: str = Field(..., description="文件内容（base64编码）")


class MessageResponse(BaseModel):
    id: str = Field(..., description="消息ID")
    role: str = Field(..., description="角色：user / assistant")
    content: str = Field(..., description="消息内容")
    agent_type: str | None = Field(None, description="处理的Agent类型")
    celery_task_id: str | None = Field(None, description="异步任务ID")
    download_url: str | None = Field(None, description="下载链接")
    references: list[dict] | None = Field(None, description="知识库引用")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {
        "from_attributes": True
    }


class ConversationResponse(BaseModel):
    id: str = Field(..., description="对话ID")
    title: str = Field(..., description="对话标题")
    user_id: str | None = Field(None, description="用户ID")
    thread_id: str | None = Field(None, description="LangGraph Thread ID")
    status: str = Field(..., description="状态：active / archived")
    summary: str | None = Field(None, description="对话总结")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")

    model_config = {
        "from_attributes": True
    }


class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse = Field(..., description="对话信息")
    messages: list[MessageResponse] = Field(..., description="消息列表")


class CreateConversationRequest(BaseModel):
    title: str = Field("新对话", description="对话标题")
    user_id: str | None = Field(None, description="用户ID")
    thread_id: str | None = Field(None, description="LangGraph Thread ID")


class AddMessageRequest(BaseModel):
    role: str = Field(..., description="角色：user / assistant")
    content: str = Field(..., description="消息内容")
    agent_type: str | None = Field(None, description="处理的Agent类型")
    celery_task_id: str | None = Field(None, description="异步任务ID")
    download_url: str | None = Field(None, description="下载链接")
    references: list[dict] | None = Field(None, description="知识库引用")


class UpdateConversationRequest(BaseModel):
    title: str | None = Field(None, description="新标题")
    status: str | None = Field(None, description="状态：active / archived")
    summary: str | None = Field(None, description="对话总结")


class CreateSkillRequest(BaseModel):
    name: str = Field(..., description="Skill 名称")
    description: str = Field("", description="描述")
    category: str = Field("general", description="分类")
    tags: list[str] = Field(default_factory=list)
    version: str = Field("1.0.0")
    author: str = Field("NetOps Team")
    triggers: list[str] = Field(default_factory=list)
    instructions: str | None = Field(None, description="Markdown 指令正文")


class UpdateSkillRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    version: str | None = None
    author: str | None = None
    triggers: list[str] | None = None
    instructions: str | None = None


class SkillContentRequest(BaseModel):
    content: str = Field(..., description="SKILL.md 全文")


class SkillToggleRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用")


class SkillFileUploadRequest(BaseModel):
    folder: str = Field(..., description="scripts / references / assets")
    filename: str = Field(..., description="文件名")
    file_content: str = Field(..., description="Base64 编码的文件内容")
