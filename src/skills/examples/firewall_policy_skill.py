"""
防火墙策略生成技能

这是一个完整的 Skill 示例，展示如何基于现有工具创建技能：
1. 定义参数模型（Pydantic）
2. 关联 Celery Task
3. 注册到 SkillRegistry

使用方法：
- 在聊天界面输入："帮我生成防火墙策略，工单ID是TICKET_001"
- Supervisor 会自动识别并调用此技能
"""


from pydantic import BaseModel, Field

from src.core.celery_tasks.tasks import execute_firewall_policy_task
from src.skills.registry import skill_registry


class FirewallPolicyParams(BaseModel):
    """
    防火墙策略生成参数
    
    所有参数通过 Pydantic 自动校验
    """
    ticket_id: str | None = Field(None, description="工单号，如 TICKET_001")
    ticket_title: str | None = Field(None, description="工单标题")
    policy_file_url: str | None = Field(None, description="策略Excel文件路径或URL")
    topology_file_url: str | None = Field(None, description="拓扑文件路径或URL，可选")
    requester: str | None = Field("", description="申请人")
    assignee: str | None = Field("", description="处理人")


def get_default_policy_file():
    """获取默认的测试策略文件路径"""
    import os
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    test_file = os.path.join(BASE_DIR, "tools", "firewall-policy", "test_policy.xlsx")
    if os.path.exists(test_file):
        return test_file
    return None


async def firewall_policy_handler(params: dict) -> dict:
    """
    防火墙策略生成处理函数
    
    Args:
        params: 参数字典
        
    Returns:
        dict: 执行结果
    """
    # 补充默认值
    ticket_id = params.get("ticket_id") or f"POLICY_{params.get('thread_id', '000')}"
    ticket_title = params.get("ticket_title") or "防火墙策略生成"
    policy_file_url = params.get("policy_file_url") or get_default_policy_file()

    if not policy_file_url:
        return {
            "success": False,
            "message": "请提供策略文件路径或上传策略文件",
            "error": "policy_file_url is required",
            "execution_time_ms": 0
        }

    # 构建完整参数
    full_params = {
        "ticket_id": ticket_id,
        "ticket_title": ticket_title,
        "policy_file_url": policy_file_url,
        "topology_file_url": params.get("topology_file_url"),
        "requester": params.get("requester", ""),
        "assignee": params.get("assignee", "")
    }

    # 调用 Celery Task
    result = execute_firewall_policy_task.delay(**full_params)
    task_result = result.get(timeout=300)

    return task_result


def register_skill():
    """
    注册防火墙策略技能到 SkillRegistry
    
    此函数会被 loader.py 自动扫描并调用
    """
    from src.skills.skill_base import BaseSkill, SkillResult

    class FirewallPolicySkill(BaseSkill):
        async def execute(self, **kwargs) -> SkillResult:
            result = await firewall_policy_handler(kwargs)
            return SkillResult(**result)

    skill = FirewallPolicySkill(
        name="firewall_policy",
        description="生成防火墙配置策略文件，支持从Excel文件导入策略规则，生成可直接部署的防火墙配置",
        parameters=FirewallPolicyParams,
        handler=execute_firewall_policy_task,
        category="network",
        tags=["firewall", "policy", "configuration", "network"],
        fallback_to_rag_if_fail=True,
        enabled=True
    )

    skill_registry.register_skill(skill)


if __name__ == "__main__":
    register_skill()

    skill = skill_registry.get_skill("firewall_policy")
    if skill:
        print(f"技能注册成功: {skill.name}")
        print(f"描述: {skill.description}")
        print(f"分类: {skill.category}")
        print(f"标签: {skill.tags}")
    else:
        print("技能注册失败")
