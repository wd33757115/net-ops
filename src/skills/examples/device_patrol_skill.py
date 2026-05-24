"""
设备巡检技能

用于执行网络设备巡检操作
"""

from typing import Any

from pydantic import BaseModel, Field

from src.core.celery_tasks.tasks import execute_device_patrol_task
from src.skills.registry import skill_registry


class DevicePatrolParams(BaseModel):
    """
    设备巡检参数
    
    所有参数通过 Pydantic 自动校验
    """
    filter_params: dict[str, Any] | None = Field(None, description="过滤参数字典，包含 device_name, ip_address, group_name, model 等")
    device_name: str | None = Field(None, description="设备名称，精确匹配")
    ip_address: str | None = Field(None, description="设备IP地址")
    group_name: str | None = Field(None, description="分组名称，如'生产环境'")
    model: str | None = Field(None, description="设备型号，如'Cisco IOS'")
    ticket_id: str | None = Field(None, description="工单号，用于关联任务")
    save_baseline: bool = Field(False, description="是否保存巡检结果作为基线")


def register_skill():
    """
    注册设备巡检技能到 SkillRegistry
    
    此函数会被 loader.py 自动扫描并调用
    """
    skill_registry.register_celery_skill(
        name="device_patrol",
        description="执行网络设备巡检，检查设备状态、接口状态、CPU/内存使用率等，支持按设备名称、IP地址、分组名称或设备型号进行过滤",
        parameters=DevicePatrolParams,
        handler=execute_device_patrol_task,
        category="network",
        tags=["patrol", "inspect", "device", "network", "monitoring"],
        fallback_to_rag_if_fail=True,
        enabled=True
    )


if __name__ == "__main__":
    register_skill()

    skill = skill_registry.get_skill("device_patrol")
    if skill:
        print(f"技能注册成功: {skill.name}")
        print(f"描述: {skill.description}")
        print(f"分类: {skill.category}")
        print(f"标签: {skill.tags}")
    else:
        print("技能注册失败")
