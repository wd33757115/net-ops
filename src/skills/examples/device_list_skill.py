"""
设备列表查询技能

用于列出设备和分组信息（同步执行，无需 Celery）
"""

from typing import Any

from pydantic import BaseModel, Field

from src.skills.registry import SkillResult, skill_registry


class DeviceListParams(BaseModel):
    """
    设备列表查询参数
    """
    list_type: str = Field("devices", description="查询类型：devices（设备列表）或 groups（分组列表）")
    group_name: str | None = Field(None, description="分组名称，用于过滤设备")


async def list_devices_handler(params: dict[str, Any]) -> dict:
    """
    列出设备处理函数
    
    Args:
        params: 查询参数
        
    Returns:
        dict: 设备列表结果
    """
    try:
        from tools.netops_agent_tools import DBManager, DeviceFilter

        db_manager = DBManager()

        list_type = params.get("list_type", "devices")
        group_name = params.get("group_name")

        if list_type == "groups":
            groups = db_manager.list_groups()
            groups_data = [{"name": g} for g in groups]
            return {
                "success": True,
                "message": f"共查询到 {len(groups_data)} 个分组",
                "data": {"groups": groups_data},
                "execution_time_ms": 0
            }
        else:
            if group_name:
                filter_params = DeviceFilter(group=group_name)
            else:
                filter_params = DeviceFilter()

            devices = db_manager.get_devices_by_filter(filter_params)

            devices_data = [
                {
                    "id": d.get("device_id"),
                    "name": d.get("device_name"),
                    "ip_address": d.get("ip"),
                    "model": d.get("model")
                }
                for d in devices
            ]
            return {
                "success": True,
                "message": f"共查询到 {len(devices_data)} 个设备" + (f"（分组: {group_name}）" if group_name else ""),
                "data": {"devices": devices_data},
                "execution_time_ms": 0
            }

    except Exception as e:
        return {
            "success": False,
            "message": "查询失败",
            "error": str(e),
            "execution_time_ms": 0
        }


def register_skill():
    """
    注册设备列表查询技能到 SkillRegistry
    
    由于此技能是同步操作，直接使用 handler 函数而非 Celery Task
    """
    from src.skills.skill_base import BaseSkill

    class DeviceListSkill(BaseSkill):
        async def execute(self, **kwargs) -> SkillResult:
            result = await list_devices_handler(kwargs)
            return SkillResult(**result)

    skill = DeviceListSkill(
        name="device_list",
        description="查询设备列表或分组列表，支持按分组过滤设备",
        parameters=DeviceListParams,
        handler=list_devices_handler,
        category="network",
        tags=["list", "devices", "groups", "query"],
        fallback_to_rag_if_fail=True,
        enabled=True
    )

    skill_registry.register_skill(skill)


if __name__ == "__main__":
    register_skill()

    skill = skill_registry.get_skill("device_list")
    if skill:
        print(f"技能注册成功: {skill.name}")
        print(f"描述: {skill.description}")
        print(f"分类: {skill.category}")
        print(f"标签: {skill.tags}")
    else:
        print("技能注册失败")
