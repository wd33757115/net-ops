from django.urls import path

from . import auth
from .views import chat, conversations, health, itsm, rag, skills, system, tasks, upload

urlpatterns = [
    path("auth/login/", auth.bff_login, name="bff_login"),
    path("auth/refresh/", auth.bff_refresh, name="bff_refresh"),
    path("chat/", chat.proxy_chat, name="bff_chat"),
    path("chat/upload/", upload.proxy_chat_upload, name="bff_chat_upload"),
    path("health/", health.proxy_health, name="bff_health"),
    path("health/diagnostics/", health.proxy_health_diagnostics, name="bff_health_diagnostics"),
    path("gateway/", system.proxy_gateway_info, name="bff_gateway_info"),
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
    path("itsm/webhook/", itsm.proxy_itsm_webhook, name="bff_itsm_webhook"),
    path(
        "itsm/webhook/firewall-policy/",
        itsm.proxy_firewall_policy_webhook,
        name="bff_itsm_firewall_policy",
    ),
    path("itsm/webhook/callback/", itsm.proxy_itsm_callback, name="bff_itsm_callback"),
    path("skills/", skills.proxy_skills_list, name="bff_skills_list"),
    path("skills/stats/", skills.proxy_skills_stats, name="bff_skills_stats"),
    path("skills/reload-all/", skills.proxy_reload_all_skills, name="bff_skills_reload_all"),
    path("skills/<str:skill_name>/content/", skills.proxy_skill_content, name="bff_skill_content"),
    path("skills/<str:skill_name>/files/", skills.proxy_skill_files, name="bff_skill_files"),
    path("skills/<str:skill_name>/toggle/", skills.proxy_skill_toggle, name="bff_skill_toggle"),
    path("skills/<str:skill_name>/reload/", skills.proxy_skill_reload, name="bff_skill_reload"),
    path("skills/<str:skill_name>/", skills.proxy_skill_detail, name="bff_skill_detail"),
]
