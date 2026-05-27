"""
Supervisor v1（已废弃，仅保留供历史测试参考）。

运行时入口请使用 graph_v2.compiled_graph_v2()。
"""

import sys
from pathlib import Path
from typing import Annotated, Literal, TypedDict

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from langchain_core.messages import AIMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, StateGraph

from src.agents.knowledge_qa.agent import knowledge_qa_node
from src.common.config import get_settings
from src.common.metrics import increment_counter, observe_histogram
from src.infrastructure.db.postgres import get_postgres_saver
from src.skill_system import get_skill_system
from src.skills.registry import skill_registry
from src.skills.skill_base import SkillDecision, SkillResult

settings = get_settings()

AgentType = Literal["supervisor", "skill_executor", "knowledge_qa", "end"]


class SupervisorState(TypedDict):
    """
    Supervisor State（Skill Registry v2.0）

    messages: 对话历史（LangGraph 标准字段，使用 add_messages reducer）
    next_agent: 路由决策结果（supervisor / skill_executor / knowledge_qa / end）
    context: 上下文数据（RAG 检索结果等）
    source: 请求来源（chat / itsm_webhook）
    task_id: 任务追踪 ID
    celery_task_id: Celery 异步任务 ID
    skill_decision: LLM 结构化决策结果（SkillDecision）
    skill_result: 技能执行结果（SkillResult）
    fallback_to_rag: 是否回退到 RAG
    knowledge_references: RAG 检索引用
    uploaded_file_path: 上传文件路径（用于防火墙策略生成等场景）
    ticket_id: ITSM 工单 ID
    thread_id: 线程 ID（对话标识）
    metadata_filters: RAG 元数据过滤条件
    """
    messages: Annotated[list, "add_messages"]
    next_agent: AgentType | None
    context: str | None
    source: str | None
    task_id: str | None
    celery_task_id: str | None
    knowledge_references: list | None
    uploaded_file_path: str | None
    ticket_id: str | None
    thread_id: str | None
    metadata_filters: dict | None
    skill_decision: SkillDecision | None
    skill_result: SkillResult | None
    fallback_to_rag: bool | None
    async_mode: bool | None
    agent_type: str | None


# 初始化 DeepSeek LLM（缩短超时时间到15秒，避免卡死）
llm = ChatDeepSeek(
    model=settings.LLM_MODEL,
    temperature=0.05,
    api_key=settings.DEEPSEEK_API_KEY,
    request_timeout=30
)

# Bind LLM with structured output
llm_with_structured_output = llm.with_structured_output(SkillDecision, method="function_calling")


def supervisor_node(state: SupervisorState) -> SupervisorState:
    """
    Supervisor Agent 节点：纯 LLM 决策

    【单阶段决策架构】
    - 直接将所有技能列表交给 LLM
    - LLM 根据用户意图选择合适的技能
    - 决定是否调用技能或走 RAG

    设计原则：
    1. 用户输入完整的自然语言
    2. LLM 理解意图和提取参数
    3. 失败时走 RAG 兜底
    """
    import time
    t_start = time.time()

    query = state["messages"][-1].content
    source = state.get("source", "chat")
    uploaded_file_path = state.get("uploaded_file_path")
    ticket_id = state.get("ticket_id", "")

    print(f"\n[Supervisor Agent v4.0] source:{source} | Routing query: {query[:80]}...")

    print("   [Phase 1] Prefilter skills (embedding)...")
    candidates_for_llm = skill_registry.get_top_skills_for_llm(query, top_n=5)

    if not candidates_for_llm or candidates_for_llm == "无可用技能":
        decision = SkillDecision(
            reasoning="无可用技能，走 RAG 兜底",
            skill_name=None,
            parameters={},
            fallback_to_rag=True
        )
        final_decision = "knowledge_qa"
        print(f"   - Final routing decision -> {final_decision.upper()}")
        increment_counter("skill_routing_total", tags={"result": "no_skill"})
        observe_histogram("skill_routing_duration_ms", (time.time() - t_start) * 1000)
        return {
            **state,
            "next_agent": final_decision,
            "source": source,
            "skill_decision": decision,
            "fallback_to_rag": decision.fallback_to_rag
        }

    print("   [Phase 2] LLM decision (judge + params)...")

    prompt = f"""你是一个专业的运维助手，请在候选 Skill 中选择一个最合适的来处理用户请求，并提取执行所需参数。

【用户请求】
{query}

【上下文信息】
- uploaded_file_path: {uploaded_file_path or '无'}

【候选 Skills（只允许从这里选择）】
{candidates_for_llm}

【任务】
1. 如果用户请求是知识性问题（解释概念、原理、排查思路、方法论），不调用 Skill：skill_name=null 且 fallback_to_rag=true
2. 如果是操作任务，从候选 Skills 中选择一个最合适的 Skill
3. 从用户自然语言中提取参数；如果用户提到工单号/工单ID，提取为 ticket_id
4. 如果 uploaded_file_path 存在，尽量填充到候选 Skill 的文件类入参中（如 policy_file_url / file_path / uploaded_file_path 等）
5. 不要编造文件路径/URL；缺失就留空，让系统提示用户上传/补充

【输出要求】
请输出结构化的决策结果，包括：
- reasoning: 你的思考过程（详细说明为什么选这个技能或为什么走 RAG）
- skill_name: 选择的技能名称或 null
- parameters: 提取的参数字典
- fallback_to_rag: 是否走 RAG
"""

    try:
        # 使用 with_structured_output 强制 LLM 输出结构化数据
        decision = llm_with_structured_output.invoke(prompt)

        print("   - LLM structured decision:")
        print(f"     * reasoning: {decision.reasoning}")
        print(f"     * skill_name: {decision.skill_name}")
        print(f"     * parameters: {decision.parameters}")
        print(f"     * fallback_to_rag: {decision.fallback_to_rag}")

    except Exception as e:
        print(f"   - LLM structured output failed, falling back to RAG: {e}")
        # LLM 失败时直接走 RAG
        decision = SkillDecision(
            reasoning=f"LLM 调用失败，走 RAG 兜底: {str(e)[:80]}",
            skill_name=None,
            parameters={},
            fallback_to_rag=True
        )

    if decision.skill_name and not decision.fallback_to_rag:
        selected_skill_name = decision.skill_name
        try:
            skill_system = get_skill_system()
            instructions = skill_system.get_skill_instructions(selected_skill_name)
            if instructions:
                refinement_prompt = f"""你将执行一个 Skill。请严格遵循该 Skill 的指令，检查并补全参数。

【Skill 指令】
{instructions}

【用户请求】
{query}

【上下文信息】
- uploaded_file_path: {uploaded_file_path or '无'}

【当前已提取参数】
{decision.parameters}

【任务】
1. 保持 skill_name 不变
2. 补全/纠正 parameters，使其满足该 Skill 的输入要求
3. 如果该 Skill 不适合本次请求，设置 skill_name=null 且 fallback_to_rag=true
4. 不要编造文件路径/URL；缺失就保留为空值
"""
                refined = llm_with_structured_output.invoke(refinement_prompt)
                if refined.skill_name is None:
                    decision = refined
                else:
                    refined.skill_name = selected_skill_name
                    decision = refined
        except Exception as e:
            print(f"   - Skill instruction refinement skipped: {e}")

    # 确定路由目标
    if decision.skill_name:
        final_decision = "skill_executor"
    else:
        final_decision = "knowledge_qa"

    # =========================================================================
    # 参数合并：把 uploaded_file_path 合并到参数中
    # =========================================================================
    if final_decision == "skill_executor" and decision.skill_name:
        try:
            skill = skill_registry.get_skill(decision.skill_name)
            if skill and uploaded_file_path:
                keys = set(getattr(skill.parameters, "model_fields", {}).keys())
                if "uploaded_file_path" in keys and not decision.parameters.get("uploaded_file_path"):
                    decision.parameters["uploaded_file_path"] = uploaded_file_path
                for file_key in ("policy_file_url", "file_path", "input_file"):
                    if file_key in keys and not decision.parameters.get(file_key):
                        decision.parameters[file_key] = uploaded_file_path
            if skill and ticket_id:
                keys = set(getattr(skill.parameters, "model_fields", {}).keys())
                if "ticket_id" in keys and not decision.parameters.get("ticket_id"):
                    decision.parameters["ticket_id"] = ticket_id
        except Exception as e:
            print(f"   - Context merge skipped: {e}")

    if decision.skill_name and not decision.fallback_to_rag:
        increment_counter("skill_routing_total", tags={"result": "skill_hit"})
    else:
        increment_counter("skill_routing_total", tags={"result": "rag_fallback"})

    observe_histogram("skill_routing_duration_ms", (time.time() - t_start) * 1000)
    print(f"   - Final routing decision -> {final_decision.upper()}")

    return {
        **state,
        "next_agent": final_decision,
        "source": source,
        "skill_decision": decision,
        "fallback_to_rag": decision.fallback_to_rag
    }


def skill_executor_node(state: SupervisorState) -> SupervisorState:
    """
    Skill 执行节点（Celery 异步，通过 asyncio.run 调用）

    职责：
    1. 从 state["skill_decision"] 中获取 LLM 的决策
    2. 通过 asyncio.run 调用 skill_registry.async_execute_skill（Celery 非阻塞轮询）
    3. 将技能执行结果（download_url、log、status 等）追加到消息历史
    4. 更新 state["context"] 和 state["skill_result"]
    5. 执行失败时自动 fallback 到 RAG

    状态更新：
    - messages: 追加 AI 消息（包含执行结果、下载链接等）
    - skill_result: 存储 SkillResult 对象
    - context: 更新上下文信息
    - celery_task_id: 记录 Celery 任务 ID
    - next_agent: 成功 -> end，失败 -> knowledge_qa
    """
    import asyncio as _asyncio
    import time

    t_start = time.time()
    decision = state.get("skill_decision")

    if not decision:
        print("[Skill Executor] No skill decision found, fallback to RAG")
        increment_counter("skill_execution_total", tags={"result": "no_decision"})
        return {
            **state,
            "next_agent": "knowledge_qa",
            "fallback_to_rag": True
        }

    print(f"\n[Skill Executor] Async executing skill: {decision.skill_name}")
    print(f"               Parameters: {decision.parameters}")

    # 权限检查（非阻断：仅记录警告日志，不拦截正常请求）
    try:
        from src.skill_system.security import get_security_manager
        auth_ok = get_security_manager().check_permission(decision.skill_name, "USER")
        if not auth_ok:
            print(f"[Skill Executor] WARN: 权限不足 ({decision.skill_name})，继续执行")
            increment_counter("skill_execution_total", tags={"result": "unauthorized_pass"})
    except Exception:
        pass  # 权限系统不可用时继续正常运行

    try:
        if state.get("async_mode", False):
            result = skill_registry.submit_skill_task(decision)
            celery_task_id = result.data.get("celery_task_id") if result.data else None

            result_content = "任务已提交，正在后台处理...\n\n"
            result_content += f"Skill Name: {decision.skill_name}\n"
            if celery_task_id:
                result_content += f"Task ID: {celery_task_id}\n"
                result_content += f"Query Endpoint: /api/v1/tasks/{celery_task_id}\n"

            if not celery_task_id and result.download_url:
                result_content += "\n[已完成] 任务已同步执行完成\n"
                result_content += f"Download URL: {result.download_url}\n"
                result_content += f"Result: {result.message}\n"

            new_message = AIMessage(content=result_content)

            context_update = f"技能 {decision.skill_name} 已提交后台执行。"

            increment_counter("skill_execution_total", tags={"result": "async_submitted"})
            observe_histogram("skill_execution_duration_ms", (time.time() - t_start) * 1000)
            return {
                **state,
                "skill_result": result,
                "context": context_update,
                "celery_task_id": celery_task_id,
                "download_url": result.download_url,
                "messages": state["messages"] + [new_message],
                "next_agent": "end",
                "agent_type": "skill_executor",
                "fallback_to_rag": False
            }

        # [Celery] async execution via asyncio.run (non-blocking Celery polling)
        try:
            loop = _asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            result = _asyncio.run(skill_registry.async_execute_skill(decision))
        except RuntimeError:
            result = _asyncio.run(skill_registry.async_execute_skill(decision))

        print(f"[Skill Executor] Result: success={result.success}, message={result.message}")
        if result.download_url:
            print(f"[Skill Executor] Download URL: {result.download_url}")

        # 提取 Celery task_id（如果存在）
        celery_task_id = None
        if result.data:
            celery_task_id = result.data.get("celery_task_id")

        # 构建格式化的结果消息（用户可见）
        result_content = "[OK] Skill execution completed!\n\n"
        result_content += f"Skill Name: {decision.skill_name}\n"
        result_content += f"Result: {result.message}\n"

        if result.data:
            # 过滤内部字段，只展示有意义的数据
            display_data = {k: v for k, v in result.data.items()
                           if not k.startswith("_") and k not in ("fallback_to_rag", "celery_task_id")}
            if display_data:
                result_content += f"Data: {display_data}\n"

        if result.download_url:
            result_content += f"Download URL: {result.download_url}\n"

        if result.error:
            result_content += f"WARNING: {result.error}\n"

        if result.execution_time_ms:
            result_content += f"Duration: {result.execution_time_ms}ms\n"

        new_message = AIMessage(content=result_content)

        # 检查是否需要 fallback 到 RAG
        fallback_to_rag = result.data.get("fallback_to_rag", False) if result.data else False

        # 构建上下文字符串
        context_update = f"技能 {decision.skill_name} 执行{'成功' if result.success else '失败'}。{result.message}"

        result_tag = "success" if result.success else "error"
        increment_counter("skill_execution_total", tags={"result": result_tag})
        observe_histogram("skill_execution_duration_ms", (time.time() - t_start) * 1000)

        return {
            **state,
            "skill_result": result,
            "context": context_update,
            "celery_task_id": celery_task_id,
            "messages": state["messages"] + [new_message],
            "next_agent": "knowledge_qa" if fallback_to_rag else "end",
            "agent_type": "skill_executor",
            "fallback_to_rag": fallback_to_rag
        }

    except Exception as e:
        error_msg = f"技能执行异常: {str(e)}"
        print(f"[Skill Executor] Error: {error_msg}")

        increment_counter("skill_execution_total", tags={"result": "exception"})
        observe_histogram("skill_execution_duration_ms", (time.time() - t_start) * 1000)

        new_message = AIMessage(content=f"[FAIL] Skill execution failed: {error_msg}\n\nFalling back to RAG knowledge base...")

        return {
            **state,
            "skill_result": SkillResult(
                success=False,
                message="技能执行失败",
                error=error_msg
            ),
            "context": f"技能执行异常: {error_msg}",
            "messages": state["messages"] + [new_message],
            "next_agent": "knowledge_qa",
            "agent_type": "skill_executor",
            "fallback_to_rag": True
        }


def knowledge_qa_node_wrapper(state: SupervisorState) -> SupervisorState:
    """
    RAG 问答节点包装器

    职责：
    1. 调用 knowledge_qa_node 进行 RAG 检索和问答
    2. 将检索到的引用（knowledge_references）写入 state
    3. 保持与原有 knowledge_qa_node 的兼容性
    4. 异常时返回友好的错误消息

    状态更新：
    - messages: 追加 RAG 回答
    - knowledge_references: RAG 检索引用列表
    - next_agent: end（对话终止）
    """
    print("\n[RAG Node] Processing query through RAG")

    try:
        result = knowledge_qa_node(state)

        if "messages" in result:
            print("[RAG Node] Messages updated successfully")
        if "knowledge_references" in result:
            print(f"[RAG Node] References found: {len(result.get('knowledge_references', []))}")

        return {
            **state,
            **result,
            "next_agent": "end",
            "agent_type": "knowledge_qa"
        }
    except Exception as e:
        print(f"[RAG Node] Error: {str(e)}")

        new_message = AIMessage(content=f"[FAIL] RAG query failed: {str(e)}\n\nPlease try again later or contact administrator.")

        return {
            **state,
            "messages": state["messages"] + [new_message],
            "next_agent": "end"
        }


def route_supervisor(state: SupervisorState) -> AgentType:
    """
    LangGraph 条件路由函数

    根据 state["next_agent"] 决定下一个节点：
    - skill_executor: 调用技能执行节点
    - knowledge_qa: 调用 RAG 问答节点
    - end: 终止对话

    此函数同时用于 supervisor 和 skill_executor 两个节点后的路由。
    """
    return state.get("next_agent") or "end"


def build_supervisor_graph(checkpointer=None):
    """
    构建 Supervisor StateGraph

    采用标准 3-Node 架构：
    ┌─────────────┐
    │ Supervisor   │ ← 入口节点，意图识别 + 路由决策
    │   Node       │
    └──────┬──────┘
           │
           ├─ skill_name 不为空 ──→ ┌─────────────────┐
           │                        │ Skill Executor   │
           │                        │   Node           │
           │                        └────────┬─────────┘
           │                                 │
           │                    ┌────────────┼────────────┐
           │                    │ 成功       │ 失败        │
           │                    ▼            ▼             │
           │                  END      ┌──────────────┐   │
           │                          │ Knowledge QA  │   │
           │                          │   Node        │   │
           ├─ skill_name 为空 ──────→ └──────┬───────┘   │
           │                                 │            │
           │                                 ▼            │
           │                               END            │

    参数：
        checkpointer: LangGraph Checkpointer（PostgreSQL / Memory）

    返回：
        compiled_graph: 编译后的 LangGraph 可执行图
    """
    # 创建 StateGraph，指定状态类型
    workflow = StateGraph(SupervisorState)

    # 添加三个核心节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("skill_executor", skill_executor_node)
    workflow.add_node("knowledge_qa", knowledge_qa_node_wrapper)

    # 设置入口节点
    workflow.set_entry_point("supervisor")

    # supervisor 节点后的条件路由
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "skill_executor": "skill_executor",
            "knowledge_qa": "knowledge_qa",
            "end": END,
        }
    )

    # skill_executor 节点后的条件路由（成功 → END，失败 → knowledge_qa）
    workflow.add_conditional_edges(
        "skill_executor",
        route_supervisor,
        {
            "knowledge_qa": "knowledge_qa",
            "end": END,
        }
    )

    # knowledge_qa 节点后直接到 END
    workflow.add_edge("knowledge_qa", END)

    # 如果没有提供 checkpointer，使用 MemorySaver 作为开发环境默认值
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        print("[INFO] [Supervisor] Using Memory Checkpointer (Dev Mode)")
        print("[INFO] [Supervisor] For Production: Set USE_POSTGRES=true in .env")

    # 编译图并绑定 checkpointer
    compiled = workflow.compile(checkpointer=checkpointer)
    print("\n" + "=" * 60)
    print("[OK] Supervisor Agent v2.0 (Skill Registry) compiled successfully!")
    print("=" * 60)
    return compiled


def get_supervisor_graph():
    """
    获取编译后的 Supervisor Graph

    尝试使用 PostgreSQL checkpointer，如果不可用则降级为 MemorySaver。
    生产环境中应配置 PostgreSQL 以确保对话状态持久化。
    """
    try:
        postgres_saver = get_postgres_saver()
        return build_supervisor_graph(checkpointer=postgres_saver)
    except Exception as e:
        print(f"[WARN] PostgreSQL checkpointer not available: {e}")
        print("[WARN] Falling back to MemorySaver (sessions will not persist)")
        return build_supervisor_graph()


# 模块级 compiled_graph，支持直接 import 使用
# 用法：from src.agents.supervisor.graph import compiled_graph
# 使用懒加载避免启动时卡住
_compiled_graph = None

def compiled_graph():
    """懒加载获取编译后的 Supervisor Graph"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = get_supervisor_graph()
    return _compiled_graph


def test_supervisor_graph():
    """
    测试 Supervisor Graph v2.0

    使用方法：
    python -c "from src.agents.supervisor.graph import test_supervisor_graph; test_supervisor_graph()"
    """
    print("=" * 60)
    print("测试 Supervisor Graph v2.0")
    print("=" * 60)

    graph = get_supervisor_graph()

    print("\n[1] 测试设备列表查询...")
    state = graph.invoke({
        "messages": [HumanMessage(content="列出所有设备")],
        "source": "chat"
    })
    print("    [OK] Execution completed")
    print(f"    [OK] next_agent: {state.get('next_agent')}")

    print("\n[2] Testing skill decision...")
    if state.get("skill_decision"):
        decision = state["skill_decision"]
        print(f"    [OK] skill_name: {decision.skill_name}")
        print(f"    [OK] reasoning: {decision.reasoning[:80]}...")

    print("\n[3] Testing RAG Q&A...")
    state2 = graph.invoke({
        "messages": [HumanMessage(content="what is firewall")],
        "source": "chat"
    })
    print("    [OK] Execution completed")
    print(f"    [OK] next_agent: {state2.get('next_agent')}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_supervisor_graph()
