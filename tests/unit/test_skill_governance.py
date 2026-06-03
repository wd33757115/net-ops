"""Skill 灰度治理单元测试。"""

from src.skill_system.governance.rollout import (
    ROLLOUT_DRAFT,
    in_rollout_cohort,
    is_skill_available,
)


def test_rollout_cohort_deterministic():
    a = in_rollout_cohort("user-123", "firewall-policy-generator", 50)
    b = in_rollout_cohort("user-123", "firewall-policy-generator", 50)
    assert a == b


def test_rollout_cohort_full():
    assert in_rollout_cohort("any", "skill-a", 100) is True
    assert in_rollout_cohort("any", "skill-a", 0) is False


def test_draft_skill_not_available():
    ok, msg = is_skill_available(
        {
            "skill_name": "new-skill",
            "enabled": True,
            "deprecated": False,
            "rollout_status": ROLLOUT_DRAFT,
            "enabled_ratio": 100,
        }
    )
    assert ok is False
    assert "draft" in msg.lower() or "draft" in msg


def test_canary_ratio_blocks():
    entry = {
        "skill_name": "canary-skill",
        "enabled": True,
        "deprecated": False,
        "rollout_status": "canary",
        "enabled_ratio": 0,
    }
    ok, _ = is_skill_available(entry, user_id="u1")
    assert ok is False
