# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""将 async BFF 视图暴露为 Django 同步视图（Daphne 兼容）。"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from functools import wraps
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def sync_bff_view(async_view: F) -> F:
    @wraps(async_view)
    def wrapper(*args, **kwargs):
        return async_to_sync(async_view)(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
