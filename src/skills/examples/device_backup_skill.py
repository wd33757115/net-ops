"""
设备配置备份技能

用于执行网络设备配置备份操作
"""


from pydantic import BaseModel, Field

from src.core.celery_tasks.tasks import execute_config_backup_task
from src.skills.registry import skill_registry


class DeviceBackupParams(BaseModel):
    """
    设备配置备份参数
    
    所有参数通过 Pydantic 自动校验
    """
    device_name: str | None = Field(None, description="设备名称，精确匹配")
    ip_address: str | None = Field(None, description="设备IP地址")
    group_name: str | None = Field(None, description="分组名称，如'生产环境'")
    model: str | None = Field(None, description="设备型号，如'Cisco IOS'")
    ticket_id: str | None = Field(None, description="工单号，用于关联任务")


def register_skill():
    """
    注册设备配置备份技能到 SkillRegistry
    
    此函数会被 loader.py 自动扫描并调用
    """
    skill_registry.register_celery_skill(
        name="device_backup",
        description="执行网络设备配置备份，支持按设备名称、IP地址、分组名称或设备型号进行过滤",
        parameters=DeviceBackupParams,
        handler=execute_config_backup_task,
        category="network",
        tags=["backup", "configuration", "device", "network"],
        fallback_to_rag_if_fail=True,
        enabled=True
    )


if __name__ == "__main__":
    register_skill()

    skill = skill_registry.get_skill("device_backup")
    if skill:
        print(f"技能注册成功: {skill.name}")
        print(f"描述: {skill.description}")
        print(f"分类: {skill.category}")
        print(f"标签: {skill.tags}")
    else:
        print("技能注册失败")
