"""
Supervisor v2 — 高级协同模式

架构：pre_process → supervisor(ExecutionPlan) → orchestrator(Send fan-out)
      → skill_executor_v2(Map) → final_aggregator(Reduce) / knowledge_qa → END
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from src.agents.knowledge_qa.agent import knowledge_qa_node
from src.agents.supervisor.models_v2 import (
    ExecutionPlan,
    ExecutionPlanModel,
    SkillTaskSpec,
)
from src.common.config import get_settings
from src.common.metrics import increment_counter, observe_histogram
from src.common.ticket_utils import extract_ticket_id as _extract_ticket_id
from src.infrastructure.db.postgres import get_postgres_saver
from src.skill_system import get_skill_system
from src.skill_system.router import SkillMatch
from src.skills.registry import skill_registry
from src.skills.skill_base import SkillDecision, SkillResult

settings = get_settings()
logger = logging.getLogger(__name__)

AgentType = Literal["supervisor", "skill_executor", "knowledge_qa", "end"]
PRE_PROCESS_TOP_K = 5
# 语义路由低于此阈值不加载 Skill（避免知识问句误匹配 device-backup 等）
SEMANTIC_SKILL_MIN_CONFIDENCE = float(os.getenv("SEMANTIC_SKILL_MIN_CONFIDENCE", "0.72"))

llm = ChatDeepSeek(
    model=settings.LLM_MODEL,
    temperature=0.05,
    api_key=settings.DEEPSEEK_API_KEY,
    request_timeout=30,
)
llm_with_execution_plan = llm.with_structured_output(
    ExecutionPlanModel, method="function_calling"
)


# 新一轮用户消息时由 pre_process_node 写入，用于清空 checkpoint 中的 intermediate_results
INTERMEDIATE_RESULTS_RESET: dict[str, Any] = {"__reset_intermediate_results__": True}


def _merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(right, dict) and right.get("__reset_intermediate_results__"):
        return {}
    merged = dict(left or {})
    if right:
        merged.update(right)
    return merged


class SupervisorStateV2(TypedDict):
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
    # v2 协同字段
    skill_matches: list[SkillMatch] | None
    skill_instructions: dict[str, str] | None
    execution_plan: ExecutionPlan | None
    intermediate_results: Annotated[dict[str, Any] | None, _merge_dicts]
    loaded_skills: list[str] | None
    current_skill_task: SkillTaskSpec | None


def _get_query(state: SupervisorStateV2) -> str:
    return state["messages"][-1].content


def _route_skills(query: str, top_k: int = PRE_PROCESS_TOP_K) -> list[SkillMatch]:
    skill_system = get_skill_system()
    if skill_system.router:
        return skill_system.router.route(query, top_k=top_k)
    return skill_system.route(query, top_k=top_k)


def _has_trigger_match(skill_matches: list[SkillMatch], loaded_skills: list[str]) -> bool:
    loaded = set(loaded_skills)
    return any(
        m.skill_name in loaded
        and m.match_type == "trigger"
        and m.confidence >= 0.85
        for m in skill_matches
    )


def _is_knowledge_question(query: str) -> bool:
    """
    判断是否为知识库/方法论类问句（应走 RAG，而非低置信 Skill）。
    含明确运维动作触发词时返回 False。
    """
    q = query.strip()
    operational_patterns = [
        r"生成防火墙",
        r"防火墙策略",
        r"备份.{0,8}配置",
        r"配置备份",
        r"设备备份",
        r"执行.{0,6}巡检",
        r"设备巡检",
        r"工单号",
        r"ticket[_\s-]?id",
        r"下发",
        r"生成.{0,6}策略",
        r"公文",
        r"写.{0,4}请示",
        r"写.{0,4}通知",
        r"写.{0,4}函",
        r"写.{0,4}报告",
        r"写.{0,4}总结",
        r"写.{0,4}纪要",
        r"一份请示",
        r"一份通知",
        r"公文写作",
        r"公文审核",
    ]
    if any(re.search(p, q, re.IGNORECASE) for p in operational_patterns):
        return False

    knowledge_patterns = [
        r"怎么办",
        r"如何做",
        r"怎么做",
        r"如何",
        r"什么是",
        r"为什么",
        r"为啥",
        r"原理",
        r"步骤",
        r"排查",
        r"故障",
        r"标准操作",
        r"SOP",
        r"是什么意思",
        r"介绍",
        r"讲解",
        r"处理方法",
        r"处理流程",
    ]
    return any(re.search(p, q, re.IGNORECASE) for p in knowledge_patterns)


def _is_actionable_skill_match(match: SkillMatch) -> bool:
    """是否值得加载/执行该 Skill 匹配。"""
    if match.match_type == "trigger":
        return match.confidence >= 0.85
    if match.match_type == "tag":
        return match.confidence >= 0.75
    if match.match_type == "semantic":
        return match.confidence >= SEMANTIC_SKILL_MIN_CONFIDENCE
    return match.confidence >= 0.85


def _filter_skill_matches(query: str, matches: list[SkillMatch]) -> list[SkillMatch]:
    """过滤低置信语义匹配；知识类问句在无触发词时不保留 Skill。"""
    filtered = [m for m in matches if _is_actionable_skill_match(m)]
    if _is_knowledge_question(query) and not any(
        m.match_type == "trigger" and m.confidence >= 0.85 for m in filtered
    ):
        return []
    return filtered


def _build_heuristic_execution_plan(
    query: str,
    loaded_skills: list[str],
    skill_matches: list[SkillMatch] | None,
    uploaded_file_path: str | None,
) -> ExecutionPlan | None:
    """
    不调用 LLM 的规则化 ExecutionPlan（触发词已匹配时使用）。
    避免 API 余额不足时误走 RAG。
    """
    if not loaded_skills:
        return None

    matches_by_name = {m.skill_name: m for m in (skill_matches or [])}
    primary = None
    for name in loaded_skills:
        match = matches_by_name.get(name)
        if match and match.match_type == "trigger":
            primary = name
            break
    if not primary:
        return None

    params: dict[str, Any] = {}
    ticket_id = _extract_ticket_id(query)
    if ticket_id:
        params["ticket_id"] = ticket_id
    if uploaded_file_path:
        params["policy_file_url"] = uploaded_file_path
    if primary == "official-document-writing":
        params.setdefault("user_query", query)
        params.setdefault("action", "write")
        for doc_type in ("请示", "通知", "函", "报告", "总结", "纪要", "决定"):
            if doc_type in query:
                params.setdefault("document_type", doc_type)
                break

    match = matches_by_name.get(primary)
    reason = match.reason if match else "已加载 Skill 指令"
    return ExecutionPlan(
        reasoning=f"规则调度（免 LLM）: {reason}",
        skills=[SkillTaskSpec(skill_name=primary, parameters=params)],
        execution_mode="parallel",
        fallback_to_rag=False,
    )


def _merge_params_with_deps(
    task: SkillTaskSpec,
    intermediate_results: dict[str, Any] | None,
    uploaded_file_path: str | None,
    ticket_id: str | None,
) -> dict[str, Any]:
    params = dict(task.parameters)
    if intermediate_results:
        for dep in task.depends_on:
            dep_result = intermediate_results.get(dep)
            if isinstance(dep_result, dict):
                params.setdefault(f"{dep}_output", dep_result)
                if dep_result.get("data"):
                    params.setdefault("previous_data", dep_result["data"])
    if uploaded_file_path:
        params.setdefault("uploaded_file_path", uploaded_file_path)
    if ticket_id:
        params.setdefault("ticket_id", ticket_id)
    return params


def _successful_deps(task: SkillTaskSpec, intermediate: dict[str, Any] | None) -> bool:
    """前置依赖必须已成功执行。"""
    intermediate = intermediate or {}
    for dep in task.depends_on:
        dep_result = intermediate.get(dep)
        if not isinstance(dep_result, dict) or not dep_result.get("success"):
            return False
    return True


def _deps_satisfied(
    task: SkillTaskSpec,
    completed: set[str],
    intermediate: dict[str, Any] | None = None,
) -> bool:
    if not all(dep in completed for dep in task.depends_on):
        return False
    return _successful_deps(task, intermediate)


def _detect_dependency_cycle(tasks: list[SkillTaskSpec]) -> bool:
    graph: dict[str, list[str]] = {t.skill_name: list(t.depends_on) for t in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            if dfs(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(dfs(name) for name in graph)


def _next_runnable_task(
    tasks: list[SkillTaskSpec],
    completed: set[str],
    intermediate: dict[str, Any] | None = None,
) -> SkillTaskSpec | None:
    for task in tasks:
        if task.skill_name in completed:
            continue
        if _deps_satisfied(task, completed, intermediate):
            return task
    return None


def _parallel_runnable_tasks(
    pending: list[SkillTaskSpec],
    completed: set[str],
    intermediate: dict[str, Any] | None,
) -> list[SkillTaskSpec]:
    return [t for t in pending if _deps_satisfied(t, completed, intermediate)]


def _should_fallback_to_rag_after_skills(state: SupervisorStateV2) -> bool:
    """全部 Skill 失败且计划或 Skill 元数据允许 RAG 兜底。"""
    plan = state.get("execution_plan")
    intermediate = state.get("intermediate_results") or {}
    if not plan or not intermediate:
        return False

    tasks = _filter_conditional_tasks(plan, state)
    executed = [t for t in tasks if t.skill_name in intermediate]
    if not executed:
        return False

    if any(intermediate.get(t.skill_name, {}).get("success") for t in executed):
        return False

    if plan.fallback_to_rag:
        return True

    for task in executed:
        skill = skill_registry.get_skill(task.skill_name)
        if skill and skill.fallback_to_rag_if_fail:
            return True
    return False


def _filter_conditional_tasks(plan: ExecutionPlan, state: SupervisorStateV2) -> list[SkillTaskSpec]:
    if plan.execution_mode != "conditional":
        return list(plan.skills)
    intermediate = state.get("intermediate_results") or {}
    filtered: list[SkillTaskSpec] = []
    for task in plan.skills:
        condition_key = plan.conditions.get(task.skill_name)
        if not condition_key:
            filtered.append(task)
            continue
        for dep in task.depends_on:
            dep_result = intermediate.get(dep)
            if isinstance(dep_result, dict) and dep_result.get("success"):
                filtered.append(task)
                break
    return filtered


def _build_send_payload(state: SupervisorStateV2, task: SkillTaskSpec) -> dict[str, Any]:
    plan = state.get("execution_plan")
    reasoning = plan.reasoning if plan else "orchestrator dispatch"
    params = _merge_params_with_deps(
        task,
        state.get("intermediate_results"),
        state.get("uploaded_file_path"),
        state.get("ticket_id") or "",
    )
    messages = state.get("messages") or []
    if messages:
        params.setdefault("user_query", messages[-1].content)
    return {
        "current_skill_task": task,
        "skill_decision": SkillDecision(
            reasoning=reasoning,
            skill_name=task.skill_name,
            parameters=params,
            fallback_to_rag=False,
        ),
    }


def pre_process_node(state: SupervisorStateV2) -> SupervisorStateV2:
    """SemanticRouter 多匹配 + SkillLoader 批量加载（Progressive Disclosure）。"""
    t_start = time.time()
    query = _get_query(state)
    print(f"\n[Supervisor v2] pre_process_node | query: {query[:80]}...", flush=True)

    raw_matches = _route_skills(query, top_k=PRE_PROCESS_TOP_K)
    matches = _filter_skill_matches(query, raw_matches)
    if len(matches) < len(raw_matches):
        print(
            f"   pre_process 过滤弱匹配 {len(raw_matches)} → {len(matches)} "
            f"(知识问句或语义低于 {SEMANTIC_SKILL_MIN_CONFIDENCE})"
        )
    skill_system = get_skill_system()
    skill_instructions: dict[str, str] = {}
    loaded_skills: list[str] = []

    for match in matches:
        try:
            content = (skill_system.get_skill_instructions(match.skill_name) or "").strip()
            if content:
                skill_instructions[match.skill_name] = content
                loaded_skills.append(match.skill_name)
            else:
                logger.warning(
                    "pre_process: Skill %s 指令为空 (match=%s)",
                    match.skill_name,
                    match.match_type,
                )
        except Exception as exc:
            logger.exception(
                "pre_process: 加载 Skill %s 失败: %s",
                match.skill_name,
                exc,
            )

    duration_ms = (time.time() - t_start) * 1000
    observe_histogram("supervisor_v2_pre_process_duration_ms", duration_ms)
    increment_counter("supervisor_v2_pre_process_total", tags={"loaded_count": str(len(loaded_skills))})
    print(
        f"   pre_process_node 匹配 {len(matches)} 个 / 加载 {len(loaded_skills)} 个 Skill，"
        f"耗时 {duration_ms:.0f}ms"
    )

    ticket_id = _extract_ticket_id(query) or state.get("ticket_id")
    ticket_update = {}
    if ticket_id:
        ticket_update["ticket_id"] = ticket_id

    return {
        **state,
        **ticket_update,
        "skill_matches": matches,
        "skill_instructions": skill_instructions,
        "loaded_skills": loaded_skills,
        # 每轮对话清空 Skill 执行结果，避免复用同 thread checkpoint 中的旧失败/成功记录
        "intermediate_results": INTERMEDIATE_RESULTS_RESET,
    }


def supervisor_node_v2(state: SupervisorStateV2) -> SupervisorStateV2:
    """Supervisor 决策节点：仅输出 ExecutionPlan，不直接执行 Skill。"""
    t_start = time.time()
    query = _get_query(state)
    uploaded_file_path = state.get("uploaded_file_path")
    skill_instructions = state.get("skill_instructions") or {}
    loaded_skills = state.get("loaded_skills") or []

    print(f"\n[Supervisor v2] supervisor_node | 已加载 Skill: {loaded_skills}")

    if not loaded_skills:
        plan = ExecutionPlan(
            reasoning="无匹配 Skill，走 RAG 兜底",
            skills=[],
            execution_mode="parallel",
            fallback_to_rag=True,
        )
        increment_counter("supervisor_v2_plan_total", tags={"result": "rag_fallback"})
        observe_histogram("supervisor_v2_supervisor_duration_ms", (time.time() - t_start) * 1000)
        return {**state, "execution_plan": plan, "fallback_to_rag": True, "next_agent": "knowledge_qa"}

    skill_matches = state.get("skill_matches") or []
    heuristic_plan = _build_heuristic_execution_plan(
        query, loaded_skills, skill_matches, uploaded_file_path
    )
    # 仅触发词命中时用规则调度；低置信语义匹配改走 RAG / LLM 规划
    use_rule_plan = heuristic_plan is not None and _has_trigger_match(
        skill_matches, loaded_skills
    )

    if use_rule_plan:
        print(
            f"   ExecutionPlan: 规则调度 → {heuristic_plan.skills[0].skill_name} "
            f"params={heuristic_plan.skills[0].parameters}"
        )
        increment_counter("supervisor_v2_plan_total", tags={"result": "rule_plan"})
        observe_histogram("supervisor_v2_supervisor_duration_ms", (time.time() - t_start) * 1000)
        return {
            **state,
            "execution_plan": heuristic_plan,
            "fallback_to_rag": False,
            "next_agent": "skill_executor",
        }

    skills_block = []
    for name in loaded_skills:
        instructions = skill_instructions.get(name, "")
        skills_block.append(f"### Skill: {name}\n{instructions[:2000]}")

    prompt = f"""你是 NetOps 多 Skill 协同调度器。根据用户请求，从已加载的 Skill 中制定 ExecutionPlan。

【用户请求】
{query}

【上下文】
- uploaded_file_path: {uploaded_file_path or '无'}

【已加载 Skills 指令（Progressive Disclosure）】
{chr(10).join(skills_block)}

【任务】
1. 知识性问题（概念/原理/方法论）→ skills=[] 且 fallback_to_rag=true
2. 单 Skill 任务 → skills 仅含 1 项，execution_mode=parallel
3. 多 Skill 可并行 → execution_mode=parallel，depends_on=[]
4. 有先后顺序（A 结果供 B 使用）→ execution_mode=sequential，B.depends_on 含 A 的 skill_name
5. 条件执行 → execution_mode=conditional，在 conditions 中描述触发条件
6. 从用户话术中提取 parameters；不要编造文件路径

【输出】
reasoning、skills（skill_name/parameters/depends_on）、execution_mode、conditions、fallback_to_rag
"""

    try:
        plan_model = llm_with_execution_plan.invoke(prompt)
        plan = ExecutionPlan.from_model(plan_model)
        print(f"   ExecutionPlan: mode={plan.execution_mode}, skills={[s.skill_name for s in plan.skills]}")
    except Exception as exc:
        print(f"   ExecutionPlan LLM 失败: {exc}")
        if heuristic_plan and heuristic_plan.skills:
            plan = heuristic_plan
            plan.reasoning = f"{plan.reasoning}（LLM 不可用: {str(exc)[:80]}）"
            print(f"   回退规则调度 → {plan.skills[0].skill_name}")
        else:
            plan = ExecutionPlan(
                reasoning=f"LLM 决策失败: {str(exc)[:80]}",
                skills=[],
                fallback_to_rag=True,
            )

    tag = "skill_plan" if plan.skills and not plan.fallback_to_rag else "rag_fallback"
    increment_counter("supervisor_v2_plan_total", tags={"result": tag})
    observe_histogram("supervisor_v2_supervisor_duration_ms", (time.time() - t_start) * 1000)

    next_agent: AgentType = "knowledge_qa" if plan.fallback_to_rag or not plan.skills else "skill_executor"
    return {
        **state,
        "execution_plan": plan,
        "fallback_to_rag": plan.fallback_to_rag,
        "next_agent": next_agent,
    }


def orchestrator_dispatch(state: SupervisorStateV2):
    """
    动态编排：parallel 多 Send fan-out；sequential/conditional 单 Send 或结束。
    返回 Send 列表 / 节点名。
    """
    plan = state.get("execution_plan")
    if not plan or plan.fallback_to_rag or not plan.skills:
        return "knowledge_qa"

    tasks = _filter_conditional_tasks(plan, state)
    if not tasks:
        print("[Supervisor v2] orchestrator: 无可执行任务 → final_aggregator")
        return "final_aggregator"

    if _detect_dependency_cycle(tasks):
        logger.error("[Supervisor v2] orchestrator: 检测到 depends_on 循环依赖")
        return "final_aggregator"

    completed = set((state.get("intermediate_results") or {}).keys())
    intermediate = state.get("intermediate_results") or {}

    if plan.execution_mode == "parallel":
        pending = [t for t in tasks if t.skill_name not in completed]
        if not pending:
            print(
                f"[Supervisor v2] orchestrator: Skill 已在 intermediate_results 中 {completed}，"
                "跳过 fan-out（若为本轮新消息仍出现，请确认 pre_process 已清空 checkpoint）"
            )
            return "final_aggregator"

        runnable = _parallel_runnable_tasks(pending, completed, intermediate)
        if not runnable:
            print("[Supervisor v2] orchestrator: 并行任务被依赖阻塞或前置失败 → final_aggregator")
            return "final_aggregator"

        print(f"[Supervisor v2] orchestrator fan-out 并行执行 {len(runnable)} 个 Skill")
        increment_counter(
            "supervisor_v2_orchestrator_fanout_total",
            tags={"mode": "parallel", "count": str(len(runnable))},
        )
        return [Send("skill_executor_v2", _build_send_payload(state, task)) for task in runnable]

    next_task = _next_runnable_task(
        [t for t in tasks if t.skill_name not in completed],
        completed,
        intermediate,
    )
    if not next_task:
        return "final_aggregator"

    print(f"[Supervisor v2] orchestrator fan-out 顺序执行 Skill: {next_task.skill_name}")
    increment_counter("supervisor_v2_orchestrator_fanout_total", tags={"mode": plan.execution_mode, "count": "1"})
    return Send("skill_executor_v2", _build_send_payload(state, next_task))


async def _execute_skill_decision(decision: SkillDecision, async_mode: bool) -> SkillResult:
    if async_mode:
        return skill_registry.submit_skill_task(decision)
    try:
        asyncio.get_running_loop()
        import nest_asyncio

        nest_asyncio.apply()
        return await skill_registry.async_execute_skill(decision)
    except RuntimeError:
        return await skill_registry.async_execute_skill(decision)


def skill_executor_v2_node(state: SupervisorStateV2) -> SupervisorStateV2:
    """单 Skill 执行实例，读写 intermediate_results 共享上下文。"""
    t_start = time.time()
    decision = state.get("skill_decision")
    task = state.get("current_skill_task")
    skill_name = (task.skill_name if task else None) or (decision.skill_name if decision else None)

    if not decision or not skill_name:
        print("[Supervisor v2] skill_executor_v2: 无决策，跳过")
        return state

    print(f"\n[Supervisor v2] skill_executor_v2 | Skill: {skill_name}", flush=True)
    print(f"               Parameters: {decision.parameters}", flush=True)

    try:
        from src.skill_system.security import get_security_manager

        if not get_security_manager().check_permission(skill_name, "USER"):
            print(f"[Supervisor v2] WARN: 权限不足 ({skill_name})，继续执行")
    except Exception:
        pass

    try:
        result = asyncio.run(_execute_skill_decision(decision, bool(state.get("async_mode"))))
        payload = {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "download_url": result.download_url,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
        }
        tag = "success" if result.success else "error"
        increment_counter("supervisor_v2_skill_execution_total", tags={"result": tag, "skill": skill_name})
        observe_histogram("supervisor_v2_skill_execution_duration_ms", (time.time() - t_start) * 1000)
        print(f"[Supervisor v2] skill_executor_v2 完成: {skill_name} success={result.success}")

        return {
            "intermediate_results": {skill_name: payload},
        }
    except Exception as exc:
        error_msg = f"技能执行异常: {exc}"
        print(f"[Supervisor v2] skill_executor_v2 失败: {error_msg}")
        increment_counter("supervisor_v2_skill_execution_total", tags={"result": "exception", "skill": skill_name or "unknown"})
        return {
            "intermediate_results": {skill_name: {"success": False, "message": error_msg, "error": error_msg}},
        }


def route_after_executor_v2(state: SupervisorStateV2) -> str:
    if _should_fallback_to_rag_after_skills(state):
        print("[Supervisor v2] 全部 Skill 失败，回退 knowledge_qa")
        return "knowledge_qa"

    plan = state.get("execution_plan")
    if not plan:
        return "final_aggregator"

    completed = set((state.get("intermediate_results") or {}).keys())
    intermediate = state.get("intermediate_results") or {}
    tasks = _filter_conditional_tasks(plan, state)
    pending = [t for t in tasks if t.skill_name not in completed]

    if plan.execution_mode == "parallel":
        if pending and _parallel_runnable_tasks(pending, completed, intermediate):
            return "orchestrator"
        return "final_aggregator"

    if pending and _next_runnable_task(pending, completed, intermediate):
        return "orchestrator"
    return "final_aggregator"


def final_aggregator_node(state: SupervisorStateV2) -> SupervisorStateV2:
    """Map-Reduce 聚合：合并所有 Skill 执行结果为用户可见回复。"""
    results = state.get("intermediate_results") or {}
    plan = state.get("execution_plan")
    lines = ["[OK] 多 Skill 协同执行完成\n"]

    if plan and plan.reasoning:
        lines.append(f"**调度说明**: {plan.reasoning}\n")

    for skill_name, result in results.items():
        if not isinstance(result, dict):
            continue
        status = "成功" if result.get("success") else "失败"
        lines.append(f"### {skill_name}")
        lines.append(f"- 状态: {status}")
        lines.append(f"- 结果: {result.get('message', '')}")
        if result.get("download_url"):
            url = result["download_url"]
            lines.append(f"- 下载: {url}")
        if result.get("error"):
            lines.append(f"- 错误: {result['error']}")
        lines.append("")

    if not results:
        lines.append("未产生 Skill 执行结果。")

    content = "\n".join(lines)
    print(f"[Supervisor v2] final_aggregator | 聚合 {len(results)} 个 Skill 结果")

    return {
        **state,
        "messages": state["messages"] + [AIMessage(content=content)],
        "context": f"协同执行完成，共 {len(results)} 个 Skill",
        "next_agent": "end",
        "agent_type": "skill_executor",
    }


def _format_rag_failure_message(exc: Exception) -> str:
    msg = str(exc)
    if "402" in msg or "Insufficient Balance" in msg:
        return (
            "**无法完成回答**：大模型 API 账户余额不足（HTTP 402）。\n\n"
            "本次请求已尝试走知识库（RAG）兜底，但生成回答同样需要调用 LLM。\n\n"
            "**建议**：\n"
            "1. 为 DeepSeek（或当前配置的 LLM）充值后重试；\n"
            "2. 运维类指令（如「生成防火墙策略」）在余额恢复后应自动匹配 Skill 执行，无需 RAG；\n"
            "3. 若仅需执行 Skill，请确认 `USE_SUPERVISOR_V2=true` 且服务已重启。\n"
        )
    return f"[FAIL] RAG 查询失败: {msg}"


def knowledge_qa_node_wrapper_v2(state: SupervisorStateV2) -> SupervisorStateV2:
    print("\n[Supervisor v2] knowledge_qa_node")
    try:
        result = knowledge_qa_node(state)
        return {**state, **result, "next_agent": "end", "agent_type": "knowledge_qa"}
    except Exception as exc:
        logger.exception("knowledge_qa 失败")
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=_format_rag_failure_message(exc))],
            "next_agent": "end",
        }


def route_after_supervisor_v2(state: SupervisorStateV2) -> str:
    plan = state.get("execution_plan")
    if not plan or plan.fallback_to_rag or not plan.skills:
        return "knowledge_qa"
    return "orchestrator"


def build_supervisor_graph_v2(checkpointer=None):
    """构建 Supervisor v2 高级协同 StateGraph。"""
    workflow = StateGraph(SupervisorStateV2)

    workflow.add_node("pre_process", pre_process_node)
    workflow.add_node("supervisor", supervisor_node_v2)
    workflow.add_node("orchestrator", lambda state: state)  # 占位，实际路由在 conditional_edges
    workflow.add_node("skill_executor_v2", skill_executor_v2_node)
    workflow.add_node("final_aggregator", final_aggregator_node)
    workflow.add_node("knowledge_qa", knowledge_qa_node_wrapper_v2)

    workflow.set_entry_point("pre_process")
    workflow.add_edge("pre_process", "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor_v2,
        {"orchestrator": "orchestrator", "knowledge_qa": "knowledge_qa"},
    )
    workflow.add_conditional_edges("orchestrator", orchestrator_dispatch)
    workflow.add_conditional_edges(
        "skill_executor_v2",
        route_after_executor_v2,
        {
            "orchestrator": "orchestrator",
            "final_aggregator": "final_aggregator",
            "knowledge_qa": "knowledge_qa",
        },
    )
    workflow.add_edge("final_aggregator", END)
    workflow.add_edge("knowledge_qa", END)

    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        print("[INFO] [Supervisor v2] Using Memory Checkpointer (Dev Mode)")

    compiled = workflow.compile(checkpointer=checkpointer)
    print("\n" + "=" * 60)
    print("[OK] Supervisor Agent v2 (Advanced Collaboration) compiled successfully!")
    print("=" * 60)
    return compiled


def get_supervisor_graph_v2():
    try:
        return build_supervisor_graph_v2(checkpointer=get_postgres_saver())
    except Exception as exc:
        print(f"[WARN] PostgreSQL checkpointer not available (v2): {exc}")
        return build_supervisor_graph_v2()


_compiled_graph_v2 = None


def compiled_graph_v2():
    global _compiled_graph_v2
    if _compiled_graph_v2 is None:
        _compiled_graph_v2 = get_supervisor_graph_v2()
    return _compiled_graph_v2
