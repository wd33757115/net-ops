from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
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


def init_db_models(engine):
    Base.metadata.create_all(bind=engine)
    print("✅ 业务表初始化完成")
