"""ITSM Webhook 插件映射测试。"""

from src.core.plugins.context_mapping import map_request_to_context
from src.core.plugins.itsm_webhook import get_itsm_webhook_registry


def test_firewall_webhook_plugin_loaded():
    reg = get_itsm_webhook_registry()
    reg.load(force=True)
    plugin = reg.get_by_route("firewall-policy")
    assert plugin is not None
    assert plugin.workflow == "itsm-firewall-change"


def test_firewall_context_mapping():
    reg = get_itsm_webhook_registry()
    reg.load(force=True)
    plugin = reg.get_by_route("firewall-policy")
    body = {
        "ticket_id": "T100",
        "ticket_title": "测试",
        "service_catalog": "安全-防火墙",
        "requester": "u1",
        "policy_file": {"url": "/tmp/p.xlsx"},
        "callback_url": "http://cb",
    }
    ctx = map_request_to_context(body, plugin.context_mapping)
    assert ctx["ticket_id"] == "T100"
    assert ctx["policy_file_url"] == "/tmp/p.xlsx"
    assert ctx["callback_url"] == "http://cb"
