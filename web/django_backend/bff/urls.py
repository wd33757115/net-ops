from django.urls import path

from . import auth
from .views import chat, conversations, health, rag, tasks

urlpatterns = [
    path("auth/login/", auth.bff_login, name="bff_login"),
    path("auth/refresh/", auth.bff_refresh, name="bff_refresh"),
    path("chat/", chat.proxy_chat, name="bff_chat"),
    path("chat/upload/", chat.proxy_chat_upload, name="bff_chat_upload"),
    path("health/", health.proxy_health, name="bff_health"),
    path("tasks/<str:task_id>/", tasks.proxy_task_status, name="bff_task_status"),
    path("conversations/", conversations.proxy_conversations, name="bff_conversations"),
    path(
        "conversations/<str:conversation_id>/",
        conversations.proxy_conversation_detail,
        name="bff_conversation_detail",
    ),
    path(
        "conversations/<str:conversation_id>/messages/",
        conversations.proxy_add_message,
        name="bff_add_message",
    ),
    path(
        "conversations/<str:conversation_id>/summarize/",
        conversations.proxy_summarize_conversation,
        name="bff_summarize_conversation",
    ),
    path("rag/search/", rag.proxy_rag_search, name="bff_rag_search"),
]
