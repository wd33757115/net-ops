"""事件 Consumer 注册表。"""

from src.core.events.consumers.audit import AuditConsumer
from src.core.events.consumers.metrics import MetricsConsumer
from src.core.events.consumers.notify import NotifyConsumer

ALL_CONSUMERS = [
    AuditConsumer(),
    NotifyConsumer(),
    MetricsConsumer(),
]
