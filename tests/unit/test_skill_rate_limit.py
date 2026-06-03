"""Skill 执行限流单元测试。"""

from unittest.mock import MagicMock, patch

from src.core.skills.rate_limit import check_skill_rate_limit


@patch("src.core.skills.rate_limit.get_redis")
@patch("src.core.skills.rate_limit.get_settings")
def test_rate_limit_allows_under_threshold(mock_settings, mock_redis):
    client = MagicMock()
    client.incr.return_value = 1
    mock_redis.return_value = client
    mock_settings.return_value.SKILL_RATE_LIMIT_ENABLED = True
    mock_settings.return_value.SKILL_RATE_LIMIT_PER_USER = 30
    mock_settings.return_value.SKILL_RATE_LIMIT_PER_SKILL = 200

    ok, msg = check_skill_rate_limit("user-1", "device-backup")
    assert ok is True
    assert msg == ""


@patch("src.core.skills.rate_limit.get_redis")
@patch("src.core.skills.rate_limit.get_settings")
def test_rate_limit_blocks_user(mock_settings, mock_redis):
    client = MagicMock()
    client.incr.return_value = 31
    mock_redis.return_value = client
    mock_settings.return_value.SKILL_RATE_LIMIT_ENABLED = True
    mock_settings.return_value.SKILL_RATE_LIMIT_PER_USER = 30
    mock_settings.return_value.SKILL_RATE_LIMIT_PER_SKILL = 200

    ok, msg = check_skill_rate_limit("user-1", "device-backup")
    assert ok is False
    assert "超限" in msg
