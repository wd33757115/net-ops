# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""网盘路径与权限单元测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.storage.folder_path import sanitize_filename, sanitize_name_segment


class TestSanitize:
    def test_reject_path_traversal(self):
        with pytest.raises(HTTPException) as exc:
            sanitize_filename("../secret.txt")
        assert exc.value.status_code == 400

    def test_reject_nested_path(self):
        with pytest.raises(HTTPException):
            sanitize_filename("a/b/c.txt")

    def test_reject_reserved_dot(self):
        with pytest.raises(HTTPException):
            sanitize_name_segment("..")

    def test_allow_normal_filename(self):
        assert sanitize_filename("report.pdf") == "report.pdf"
        assert sanitize_filename("  hello world.docx  ") == "hello_world.docx"

    def test_reject_windows_path(self):
        with pytest.raises(HTTPException):
            sanitize_filename("C:\\fake\\file.txt")
