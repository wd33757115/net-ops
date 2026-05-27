"""工单号提取单元测试。"""

from src.common.ticket_utils import extract_ticket_id


def test_extract_ticket_id_with_colon():
    assert extract_ticket_id("生成防火墙策略，工单号：test001") == "test001"


def test_extract_ticket_id_without_separator():
    assert extract_ticket_id("帮我生成防火墙策略，工单号test001") == "test001"


def test_extract_ticket_id_english():
    assert extract_ticket_id("ticket_id: ABC-99") == "ABC-99"
