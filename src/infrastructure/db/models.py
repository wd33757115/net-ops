from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TaskStatus(Base):
    __tablename__ = "netops_task_status"

    id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), index=True, comment="Celery Task ID")
    thread_id = Column(String(64), index=True, comment="LangGraph Thread ID")
    user_id = Column(String(64), index=True, nullable=True)
    source = Column(String(32), default="chat", comment="chat / itsm_webhook")
    status = Column(String(32), index=True, comment="pending / processing / completed / failed")
    agent_type = Column(String(32), comment="knowledge_qa / script_executor")
    query = Column(Text, comment="原始查询")
    parameters = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    file_url = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    itsm_callback_url = Column(String(512), nullable=True)
    itsm_callback_status = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)


class ITSMEvent(Base):
    __tablename__ = "netops_itsm_events"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(128), unique=True, index=True)
    event_type = Column(String(64), index=True)
    source_system = Column(String(128))
    title = Column(String(512))
    description = Column(Text)
    priority = Column(String(32), default="medium")
    status = Column(String(32), default="new")
    assignee = Column(String(128), nullable=True)
    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)
    result_task_id = Column(String(64), nullable=True)


class KnowledgeBaseIndex(Base):
    __tablename__ = "netops_knowledge_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(512), index=True)
    file_path = Column(String(1024))
    file_hash = Column(String(128), index=True)
    doc_type = Column(String(64), comment="sop / configuration / troubleshooting")
    meta_info = Column(JSON)
    vector_ids = Column(JSON, comment="关联向量库ID列表")
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    __tablename__ = "netops_conversations"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(512), comment="对话标题（由LLM生成）")
    user_id = Column(String(64), index=True, nullable=True, comment="用户ID")
    thread_id = Column(String(64), index=True, nullable=True, comment="LangGraph Thread ID")
    status = Column(String(32), default="active", comment="active / archived")
    summary = Column(Text, nullable=True, comment="对话总结")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        {'comment': '对话会话表 - 存储用户与Agent的对话历史'},
    )


class UserSession(Base):
    """用户登录会话（PostgreSQL，与 Django User.id 关联）。"""

    __tablename__ = "netops_user_sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=False)
    username = Column(String(128), nullable=False)
    role = Column(String(32), default="operator", comment="admin / operator / viewer")
    thread_prefix = Column(String(64), nullable=True, comment="LangGraph 用户级 thread 前缀")
    refresh_jti = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)


class AuditLogRecord(Base):
    """操作审计日志（登录、Skill 执行、Supervisor 规划等）。"""

    __tablename__ = "netops_audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=True)
    username = Column(String(128), nullable=True)
    action = Column(String(64), index=True, comment="login / logout / chat / skill_execute / ...")
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(128), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(String(32), default="success")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = "netops_messages"

    id = Column(String(64), primary_key=True, index=True)
    conversation_id = Column(String(64), index=True, comment="关联的对话ID")
    role = Column(String(32), comment="user / assistant")
    content = Column(Text, comment="消息内容")
    agent_type = Column(String(64), nullable=True, comment="处理的Agent类型")
    celery_task_id = Column(String(64), nullable=True, comment="异步任务ID")
    download_url = Column(String(512), nullable=True, comment="下载链接")
    references = Column(JSON, nullable=True, comment="知识库引用")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        {'comment': '消息表 - 存储单条对话消息'},
    )


class Team(Base):
    """团队（共享网盘归属）。"""

    __tablename__ = "netops_teams"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)


class WorkflowRun(Base):
    """多步 Workflow 运行实例（ITSM 变更闭环等）。"""

    __tablename__ = "netops_workflow_runs"

    id = Column(String(64), primary_key=True, index=True)
    template_name = Column(String(64), index=True, nullable=False)
    ticket_id = Column(String(128), index=True, nullable=True)
    source = Column(String(32), default="chat", comment="chat / itsm_webhook")
    user_id = Column(String(64), index=True, nullable=True)
    thread_id = Column(String(64), index=True, nullable=True)
    status = Column(String(32), default="pending", index=True)
    context = Column(JSON, nullable=True)
    current_step_index = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class WorkflowStepRecord(Base):
    """Workflow 单步执行记录。"""

    __tablename__ = "netops_workflow_steps"

    id = Column(String(64), primary_key=True, index=True)
    run_id = Column(String(64), index=True, nullable=False)
    step_index = Column(Integer, default=0)
    step_name = Column(String(64), nullable=False)
    skill_name = Column(String(128), nullable=False)
    celery_task_id = Column(String(64), index=True, nullable=True)
    status = Column(String(32), default="pending", index=True)
    input_artifacts = Column(JSON, nullable=True)
    output_artifacts = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    """站内通知。"""

    __tablename__ = "netops_notifications"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=False)
    title = Column(String(256), nullable=False)
    body = Column(Text, nullable=True)
    level = Column(String(32), default="info")
    payload = Column(JSON, nullable=True)
    workflow_run_id = Column(String(64), index=True, nullable=True)
    thread_id = Column(String(64), index=True, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TeamMember(Base):
    """团队成员与团队内角色。"""

    __tablename__ = "netops_team_members"

    id = Column(String(64), primary_key=True, index=True)
    team_id = Column(String(64), index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=False)
    role = Column(String(32), default="member", comment="owner / member / viewer")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)


class StorageFolder(Base):
    """虚拟目录（DB 维护层级，MinIO 用 object_key 前缀映射）。"""

    __tablename__ = "netops_storage_folders"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    parent_id = Column(String(64), index=True, nullable=True)
    owner_id = Column(String(64), index=True, nullable=True, comment="个人目录归属用户")
    team_id = Column(String(64), index=True, nullable=True, comment="团队共享目录归属团队")
    visibility = Column(String(32), default="private", comment="private / shared")
    path_cache = Column(String(1024), nullable=True, comment="物化路径缓存")
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        Index(
            "uq_storage_folder_private_root",
            "owner_id",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND visibility = 'private' AND is_deleted = false"),
        ),
        Index(
            "uq_storage_folder_shared_root",
            "team_id",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND visibility = 'shared' AND is_deleted = false"),
        ),
    )


class FileMetadata(Base):
    """文件元数据（对象存储在 MinIO）。"""

    __tablename__ = "netops_file_metadata"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(512), nullable=False)
    folder_id = Column(String(64), index=True, nullable=True)
    object_key = Column(String(1024), nullable=False, unique=True, index=True)
    owner_id = Column(String(64), index=True, nullable=True)
    team_id = Column(String(64), index=True, nullable=True)
    visibility = Column(String(32), default="private", comment="private / shared")
    content_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, default=0)
    etag = Column(String(128), nullable=True)
    status = Column(String(32), default="active", comment="pending / active")
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)


def init_db_models(engine):
    Base.metadata.create_all(bind=engine)
    print("✅ 业务表初始化完成")
