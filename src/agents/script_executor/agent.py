import os
import sys
import uuid
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from langchain_core.messages import AIMessage

from src.common.config import get_settings

settings = get_settings()

def script_executor_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Script Executor Agent - 脚本执行Agent
    - 处理脚本执行请求
    - 支持聊天触发的防火墙策略生成
    - 支持设备备份/巡检命令
    - 支持Celery异步任务分发
    """
    query = state["messages"][-1].content
    print(f"\n[Script Executor Agent] Task request: {query[:50]}...")

    if "防火墙" in query or "策略" in query or "firewall" in query.lower():
        return handle_firewall_policy_request(state, query)
    elif any(keyword in query for keyword in ["备份", "backup", "巡检", "patrol", "inspect", "device", "设备", "列出", "list", "分组", "group"]):
        return handle_device_management_request(state, query)
    else:
        return handle_generic_script_request(state, query)

def handle_firewall_policy_request(state: dict[str, Any], query: str) -> dict[str, Any]:
    """处理防火墙策略生成请求"""
    uploaded_file_path = state.get("uploaded_file_path")
    thread_id = state.get("configurable", {}).get("thread_id", str(uuid.uuid4()))

    if not uploaded_file_path:
        answer = """**防火墙策略生成服务**

📋 **当前状态**: 等待上传策略文件

**请上传策略Excel文件**，格式要求：
- 文件类型: .xlsx
- 需包含列: 序号、源IP、目的IP、端口、协议、动作
- 参考模板可在工具目录获取

**上传方式**:
1. 通过聊天界面上传文件
2. 或调用 API: POST /api/v1/chat/upload

上传后请输入: `生成防火墙策略` 或 `执行策略生成`

---

如果您已有ITSM工单，请通过Webhook触发:
POST /api/v1/itsm/webhook/firewall-policy
"""
        new_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=answer)],
            "celery_task_id": None,
            "task_status": "awaiting_file",
            "next_agent": "script_executor"
        }
        return new_state

    try:
        from src.core.celery_tasks.tasks import execute_firewall_policy_task

        local_policy_url = f"file://{uploaded_file_path}"

        # 从state中获取ticket_id，如果没有则使用默认格式
        ticket_id = state.get("ticket_id")
        print(f"[DEBUG] script_executor - ticket_id from state: {ticket_id}")
        print(f"[DEBUG] script_executor - full state keys: {state.keys()}")

        if not ticket_id:
            ticket_id = f"CHAT_{thread_id[:8]}"
            print(f"[DEBUG] script_executor - using default ticket_id: {ticket_id}")
        else:
            print(f"[DEBUG] script_executor - using provided ticket_id: {ticket_id}")

        celery_task = execute_firewall_policy_task.delay(
            ticket_id=ticket_id,
            ticket_title=f"Chat Request: {query[:30]}",
            policy_file_url=local_policy_url,
            callback_url=None,
            requester="chat_user",
            assignee="chat_user"
        )

        print(f"[DEBUG] script_executor - celery_task.id: {celery_task.task_id}")

        answer = f"""**防火墙策略生成任务已提交**

📋 **任务信息**:
- 工单号: `{ticket_id}`
- 任务ID: `{celery_task.task_id}`
- 状态: 执行中...
- 源文件: `{os.path.basename(uploaded_file_path)}`

**查询状态**:
```bash
GET /api/v1/tasks/{celery_task.task_id}
```

执行完成后将返回策略配置文件下载链接。
"""
        new_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=answer)],
            "celery_task_id": celery_task.task_id,
            "task_status": "processing",
            "next_agent": "script_executor"
        }
        return new_state

    except Exception as e:
        answer = f"""**执行失败**

❌ 错误信息: {str(e)}

请检查:
1. Redis服务是否运行 (Celery Broker)
2. 策略文件格式是否正确
3. 拓扑文件是否存在

如需帮助，请联系管理员。
"""
        new_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=answer)],
            "celery_task_id": None,
            "task_status": "failed",
            "next_agent": "script_executor"
        }
        return new_state

def handle_generic_script_request(state: dict[str, Any], query: str) -> dict[str, Any]:
    """处理通用脚本执行请求"""
    answer = """**Script Execution Service**

当前支持的脚本工具:

1. 🔥 **防火墙策略生成**
   - 描述: 根据Excel策略文件生成多厂商防火墙配置
   - 支持: 华为、H3C、天融信、山石
   - 命令示例: `生成防火墙策略`

2. 📊 **设备巡检脚本**
   - 描述: 批量执行设备健康检查
   - 命令示例: `巡检 IP 192.168.1.1` 或 `巡检 group 生产环境`

3. 🔄 **配置备份脚本**
   - 描述: 批量备份网络设备配置
   - 命令示例: `备份 group 生产环境`

4. 📋 **设备管理命令**
   - `列出所有分组` - 查看所有设备分组
   - `列出所有设备` - 查看所有设备列表

---

**使用方式**:
- 通过聊天触发: 直接输入命令
- 通过ITSM触发: POST /api/v1/itsm/webhook/firewall-policy

请输入您要执行的命令或上传相关文件。
"""
    new_state = {
        **state,
        "messages": state["messages"] + [AIMessage(content=answer)],
        "celery_task_id": None,
        "task_status": "pending",
        "next_agent": "script_executor"
    }
    return new_state

def handle_device_management_request(state: dict[str, Any], query: str) -> dict[str, Any]:
    """处理设备管理请求（备份/巡检）"""
    try:
        import sys
        from pathlib import Path

        # 正确添加项目根目录到 Python 路径
        BASE_DIR = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(BASE_DIR))
        from src.core.device_ops.loader import import_netops_agent_tools

        NetOpsToolsOrchestrator = import_netops_agent_tools().NetOpsToolsOrchestrator

        # 使用同步方式调用
        orchestrator = NetOpsToolsOrchestrator()
        result = orchestrator.execute_sync(query)

        if result.get("success"):
            message = result.get("message", "操作成功")
            celery_task_id = result.get("celery_task_id")

            if "groups" in result:
                groups_list = "\n".join([f"- {g}" for g in result["groups"]])
                answer = f"""**设备分组列表**

📋 **共 {len(result['groups'])} 个分组**:

{groups_list}

---
💡 **提示**: 您可以输入 "备份 group <分组名>" 或 "巡检 IP <IP地址>" 来执行具体操作
"""
                new_state = {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=answer)],
                    "celery_task_id": None,
                    "task_status": "completed",
                    "next_agent": "script_executor"
                }
                return new_state

            elif "devices" in result:
                devices_list = "\n".join([
                    f"- **{d['device_name']}** ({d['ip']})" +
                    (f" - {d.get('model', '未知型号')}" if d.get('model') else "")
                    for d in result["devices"][:10]
                ])
                total = result.get("total_devices", len(result["devices"]))
                answer = f"""**设备列表**

📋 **共找到 {total} 个设备**:

{devices_list}
"""
                new_state = {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=answer)],
                    "celery_task_id": None,
                    "task_status": "completed",
                    "next_agent": "script_executor"
                }
                return new_state

            elif celery_task_id:
                ticket_id = result.get("ticket_id", "unknown")
                action = result.get("action", "unknown")

                if action == "backup":
                    answer = f"""**配置备份任务已提交**

📋 **任务信息**:
- 工单号: {ticket_id}
- 任务ID: {celery_task_id}
- 状态: 执行中...

查询状态:
```bash
GET /api/v1/tasks/{celery_task_id}
```

执行完成后将返回配置文件下载链接。
"""
                else:
                    answer = f"""**设备巡检任务已提交**

📋 **任务信息**:
- 工单号: {ticket_id}
- 任务ID: {celery_task_id}
- 状态: 执行中...

查询状态:
```bash
GET /api/v1/tasks/{celery_task_id}
```

执行完成后将返回巡检报告下载链接。
"""

                new_state = {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=answer)],
                    "celery_task_id": celery_task_id,
                    "task_status": "pending",
                    "next_agent": "script_executor"
                }
                return new_state

            elif "output_files" in result:
                files = "\n".join([f"- `{f}`" for f in result.get("output_files", [])[:5]])
                answer = f"""**{result.get('action', '操作')}执行结果**

✅ **成功**: {result.get('success_devices', 0)}/{result.get('total_devices', 0)}

📁 **输出文件**:
{files}

⏱️ **耗时**: {result.get('execution_time', 0):.2f}秒
"""
                new_state = {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=answer)],
                    "celery_task_id": None,
                    "task_status": "completed",
                    "next_agent": "script_executor"
                }
                return new_state

            else:
                answer = f"""**操作结果**

✅ {message}

详细信息: {result}
"""
                new_state = {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=answer)],
                    "celery_task_id": None,
                    "task_status": "completed",
                    "next_agent": "script_executor"
                }
                return new_state

        else:
            answer = f"""**操作失败**

❌ {result.get('message', '未知错误')}

💡 {result.get('suggestion', '请检查输入格式')}
"""
            new_state = {
                **state,
                "messages": state["messages"] + [AIMessage(content=answer)],
                "celery_task_id": None,
                "task_status": "failed",
                "next_agent": "script_executor"
            }
            return new_state

    except Exception as e:
        import traceback
        print(f"[设备管理] 执行失败: {str(e)}")
        print(f"[设备管理] 详细错误: {traceback.format_exc()}")

        answer = f"""**设备管理服务错误**

❌ 错误信息: {str(e)}

可能原因:
1. 设备数据库未初始化
2. 设备凭证未配置
3. 网络连接问题

💡 **支持的操作**:
- `备份 group <分组名>` - 备份指定分组的所有设备配置
- `巡检 IP <IP地址>` - 巡检指定IP的设备
- `巡检 model <型号>` - 巡检指定型号的所有设备
- `列出所有分组` - 查看所有设备分组
- `列出所有设备` - 查看所有设备

请稍后重试或联系管理员。
"""
        new_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=answer)],
            "celery_task_id": None,
            "task_status": "failed",
            "next_agent": "script_executor"
        }
        return new_state
