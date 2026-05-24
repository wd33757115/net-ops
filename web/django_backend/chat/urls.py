
from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.proxy_chat, name='proxy_chat'),
    path('health/', views.proxy_health, name='proxy_health'),
    path('tasks/<str:task_id>/', views.proxy_task_status, name='proxy_task_status'),
    # 对话管理 API
    path('conversations/', views.proxy_conversations, name='proxy_conversations'),
    path('conversations/<str:conversation_id>/', views.proxy_conversation_detail, name='proxy_conversation_detail'),
    path('conversations/<str:conversation_id>/messages/', views.proxy_add_message, name='proxy_add_message'),
    path('conversations/<str:conversation_id>/summarize/', views.proxy_summarize_conversation, name='proxy_summarize_conversation'),
]
