# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/v1/chat$", consumers.ChatProxyConsumer.as_asgi()),
]
