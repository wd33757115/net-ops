"""
设备信息查询 Skill
演示如何创建一个简单的查询技能
"""

from typing import Any

from pydantic import BaseModel, Field

from src.skills.registry import skill_registry


# ==================== 1. 定义参数模型 ====================
class DeviceInfoParams(BaseModel):
    """
    设备信息查询参数
    """
    device_name: str | None = Field(None, description="设备名称，如'核心交换机1'")
    ip_address: str | None = Field(None, description="设备IP地址，如'192.168.1.1'")
    group_name: str | None = Field(None, description="分组名称，如'生产环境'")


# ==================== 2. 实现 Handler 函数 ====================
async def device_info_handler(params: dict[str, Any]) -> dict[str, Any]:
    """
    设备信息查询处理函数
    """
    try:
        device_name = params.get("device_name")
        ip_address = params.get("ip_address")
        group_name = params.get("group_name")

        # 模拟设备数据（实际应用中从数据库查询）
        mock_devices = [
            {
                "id": 1,
                "name": "核心交换机1",
                "ip_address": "192.168.1.1",
                "model": "H3C S5500",
                "group": "生产环境",
                "status": "在线",
                "cpu_usage": "45%",
                "memory_usage": "60%"
            },
            {
                "id": 2,
                "name": "核心交换机2",
                "ip_address": "192.168.1.2",
                "model": "H3C S5500",
                "group": "生产环境",
                "status": "在线",
                "cpu_usage": "35%",
                "memory_usage": "55%"
            },
            {
                "id": 3,
                "name": "接入交换机1",
                "ip_address": "192.168.2.1",
                "model": "Huawei S5700",
                "group": "办公环境",
                "status": "在线",
                "cpu_usage": "25%",
                "memory_usage": "40%"
            }
        ]

        # 根据条件过滤
        filtered_devices = []
        for device in mock_devices:
            match = True
            if device_name and device_name != device["name"]:
                match = False
            if ip_address and ip_address != device["ip_address"]:
                match = False
            if group_name and group_name != device["group"]:
                match = False
            if match:
                filtered_devices.append(device)

        if not filtered_devices:
            return {
                "success": True,
                "message": "未找到匹配的设备",
                "data": {"devices": []},
                "execution_time_ms": 10
            }

        return {
            "success": True,
            "message": f"查询到 {len(filtered_devices)} 个设备",
            "data": {"devices": filtered_devices},
            "execution_time_ms": 50
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"查询失败: {str(e)}",
            "error": str(e),
            "execution_time_ms": 0
        }


# ==================== 3. 注册技能 ====================
def register_skill():
    """
    注册设备信息查询技能
    """
    from src.skills.skill_base import BaseSkill, SkillResult

    class DeviceInfoSkill(BaseSkill):
        async def execute(self, **kwargs) -> SkillResult:
            result = await device_info_handler(kwargs)
            return SkillResult(**result)

    skill = DeviceInfoSkill(
        name="device_info",  # 技能名称（唯一标识）
        description="查询设备信息，支持按设备名称、IP地址、分组名称进行过滤查询",
        parameters=DeviceInfoParams,
        handler=device_info_handler,
        category="network",  # 分类：network, security, general 等
        tags=["设备信息", "查询", "网络设备"],  # 标签，用于 Embedding 匹配
        fallback_to_rag_if_fail=True,  # 失败时是否走 RAG
        enabled=True  # 是否启用
    )

    skill_registry.register_skill(skill)


# ==================== 4. 测试入口 ====================
if __name__ == "__main__":
    register_skill()
    skill = skill_registry.get_skill("device_info")
    if skill:
        print(f"✅ 技能注册成功: {skill.name}")
        print(f"   描述: {skill.description}")
        print(f"   分类: {skill.category}")
        print(f"   标签: {skill.tags}")
