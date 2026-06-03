"""chain_resolve 单元测试。"""

from src.core.skills.chain_resolve import merge_upstream_params


def test_firewall_to_change_ticket_chain():
    intermediate = {
        "firewall-policy-generator": {
            "success": True,
            "manifest": {"ticket": "REQ001"},
            "config_file_key": "firewall_policies/REQ001/p.zip",
            "download_url": "https://minio/p.zip",
            "filename": "p.zip",
            "artifacts": {
                "config_zip": {
                    "file_key": "firewall_policies/REQ001/p.zip",
                    "download_url": "https://minio/p.zip",
                }
            },
        }
    }
    params = merge_upstream_params(
        "itsm-change-ticket-writer",
        {"ticket_id": "REQ001"},
        ["firewall-policy-generator"],
        intermediate,
    )
    assert params["manifest"] == {"ticket": "REQ001"}
    assert params["config_file_key"] == "firewall_policies/REQ001/p.zip"
    assert params["config_files_url"] == "https://minio/p.zip"
    assert "firewall-policy-generator_output" in params


def test_unknown_chain_keeps_dep_output_only():
    intermediate = {"upstream-skill": {"success": True, "data": {"foo": 1}}}
    params = merge_upstream_params(
        "some-other-skill",
        {},
        ["upstream-skill"],
        intermediate,
    )
    assert params["upstream-skill_output"]["success"] is True
    assert "foo" not in params
