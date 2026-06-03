# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""工单号提取单元测试。"""

from src.common.ticket_utils import extract_ticket_id


def test_extract_ticket_id_with_colon():
    assert extract_ticket_id("生成防火墙策略，工单号：test001") == "test001"


def test_extract_ticket_id_without_separator():
    assert extract_ticket_id("帮我生成防火墙策略，工单号test001") == "test001"


def test_extract_ticket_id_english():
    assert extract_ticket_id("ticket_id: ABC-99") == "ABC-99"


def test_extract_ticket_id_req_style():
    assert extract_ticket_id("根据工单REQ2025，用策略文件生成防火墙策略") == "REQ2025"


def test_extract_ticket_id_inline_work_order():
    assert extract_ticket_id("请处理工单WO-12345") == "WO-12345"
