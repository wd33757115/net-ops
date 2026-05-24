# -*- coding: utf-8 -*-
"""
测试 Skill 安全控制
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.skill_system.security import (
    SkillSecurityManager,
    PermissionLevel,
    check_skill_permission,
    filter_sensitive_data,
    get_security_manager
)


def test_check_permission():
    """测试权限检查"""
    manager = SkillSecurityManager()

    # 设置权限
    manager.set_skill_permission("admin-skill", PermissionLevel.ADMIN)
    manager.set_skill_permission("user-skill", PermissionLevel.USER)

    # 管理员可以访问所有
    assert manager.check_permission("admin-skill", PermissionLevel.ADMIN) == True
    assert manager.check_permission("user-skill", PermissionLevel.ADMIN) == True

    # 普通用户只能访问 user-skill
    assert manager.check_permission("admin-skill", PermissionLevel.USER) == False
    assert manager.check_permission("user-skill", PermissionLevel.USER) == True

    # 访客只能访问 guest-skill
    manager.set_skill_permission("guest-skill", PermissionLevel.GUEST)
    assert manager.check_permission("guest-skill", PermissionLevel.GUEST) == True
    assert manager.check_permission("user-skill", PermissionLevel.GUEST) == False

    print("[OK] test_check_permission")


def test_filter_sensitive_data():
    """测试敏感数据过滤"""
    manager = SkillSecurityManager()

    # 正常数据
    data = {"name": "test", "value": 123}
    filtered = manager.filter_sensitive_data(data)
    assert filtered == data

    # 包含密码
    data = {"username": "admin", "password": "secret123"}
    filtered = manager.filter_sensitive_data(data)
    assert filtered["username"] == "admin"
    assert "***" in filtered["password"]

    # 嵌套数据
    data = {
        "config": {
            "api_key": "secret-api-key",
            "endpoint": "https://api.example.com"
        }
    }
    filtered = manager.filter_sensitive_data(data)
    assert "api_key" in filtered["config"]
    assert "***" in filtered["config"]["api_key"]
    assert filtered["config"]["endpoint"] == "https://api.example.com"

    print("[OK] test_filter_sensitive_data")


def test_audit_log():
    """测试审计日志"""
    manager = SkillSecurityManager()

    # 记录执行
    manager.log_execution(
        skill_name="test-skill",
        user_id="user1",
        action="execute",
        parameters={"ticket_id": "T001"},
        result="success",
        duration_ms=1000
    )

    # 获取日志
    logs = manager.get_audit_log(skill_name="test-skill")
    assert len(logs) == 1
    assert logs[0].skill_name == "test-skill"
    assert logs[0].user_id == "user1"
    assert logs[0].result == "success"

    print("[OK] test_audit_log")


def test_global_security_manager():
    """测试全局安全管理器"""
    manager1 = get_security_manager()
    manager2 = get_security_manager()

    # 应该是同一个实例
    assert manager1 is manager2

    print("[OK] test_global_security_manager")


def test_validate_parameters():
    """测试参数验证"""
    manager = SkillSecurityManager()

    # 定义 schema
    schema = {
        "required": ["name", "age"],
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        }
    }

    # 正常参数
    valid, error = manager.validate_parameters(
        {"name": "test", "age": 25},
        schema
    )
    assert valid == True
    assert error is None

    # 缺少必填参数
    valid, error = manager.validate_parameters(
        {"name": "test"},
        schema
    )
    assert valid == False
    assert "name" in error or "age" in error

    print("[OK] test_validate_parameters")


if __name__ == "__main__":
    print("=" * 50)
    print("运行 Skill 安全控制测试")
    print("=" * 50)

    test_check_permission()
    test_filter_sensitive_data()
    test_audit_log()
    test_global_security_manager()
    test_validate_parameters()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)
