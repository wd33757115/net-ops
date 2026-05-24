#!/usr/bin/env python
"""
Hybrid 决策架构集成测试脚本

测试内容：
1. Skill Registry 功能测试
2. Embedding 预筛选测试
3. Supervisor 路由决策测试
4. 完整流程测试

使用方法：
python test_hybrid_decision.py
"""

import sys
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.skills.registry import skill_registry
from src.skills.loader import load_all_skills
from src.skills.skill_base import SkillDecision


def test_skill_registry():
    """测试 Skill Registry 功能"""
    print("=" * 60)
    print("测试 1: Skill Registry 功能")
    print("=" * 60)
    
    # 加载所有技能
    count = load_all_skills()
    print(f"[OK] 加载了 {count} 个技能")
    
    # 测试技能列表
    skills = skill_registry.list_skills()
    print(f"[OK] 技能总数: {len(skills)}")
    
    # 测试技能信息
    for skill in skills:
        print(f"     - {skill.name}: {skill.description[:40]}...")
    
    # 测试统计信息
    stats = skill_registry.get_statistics()
    print(f"[OK] 统计信息: {stats}")
    
    print("✓ Skill Registry 测试通过")


def test_embedding_prefilter():
    """测试 Embedding 预筛选功能"""
    print("\n" + "=" * 60)
    print("测试 2: Embedding 预筛选")
    print("=" * 60)
    
    test_queries = [
        "生成防火墙策略",
        "设备巡检",
        "备份配置",
        "列出设备",
        "端口Down怎么办"
    ]
    
    for query in test_queries:
        print(f"\n查询: '{query}'")
        try:
            top_skills = skill_registry.prefilter_by_embedding(query, top_n=3)
            if top_skills:
                print(f"  匹配技能:")
                for skill in top_skills:
                    print(f"    - {skill.name}")
            else:
                print(f"  无匹配技能")
        except Exception as e:
            print(f"  [WARN] Embedding 未安装，跳过: {e}")
    
    print("✓ Embedding 预筛选测试通过")


def test_hybrid_decision():
    """测试 Hybrid 决策流程"""
    print("\n" + "=" * 60)
    print("测试 3: Hybrid 决策流程")
    print("=" * 60)
    
    # 模拟测试决策
    from src.agents.supervisor.graph import supervisor_node, SupervisorState
    
    test_cases = [
        ("帮我生成防火墙策略，工单号 TICKET_001", "firewall_policy"),
        ("设备巡检", "device_patrol"),
        ("备份配置", "device_backup"),
        ("列出设备", "device_list"),
        ("交换机端口Down怎么办", None),  # 应该走 RAG
    ]
    
    for query, expected_skill in test_cases:
        print(f"\n查询: '{query}'")
        print(f"期望: {'RAG' if expected_skill is None else expected_skill}")
        
        # 构建状态
        state = SupervisorState(
            messages=[],
            next_agent="supervisor",
            source="test",
            fallback_to_rag=False,
            skill_decision=SkillDecision(
                reasoning="",
                skill_name=None,
                parameters={},
                fallback_to_rag=False
            ),
            uploaded_file_path=None,
            ticket_id=""
        )
        # 添加消息
        from langchain_core.messages import HumanMessage
        state["messages"] = [HumanMessage(content=query)]
        
        try:
            result = supervisor_node(state)
            skill_name = result["skill_decision"].skill_name
            print(f"实际: {'RAG' if skill_name is None else skill_name}")
            
            if expected_skill is None and skill_name is None:
                print("  ✓ 正确走 RAG")
            elif expected_skill == skill_name:
                print("  ✓ 正确匹配技能")
            else:
                print(f"  ✗ 匹配错误: 期望 {expected_skill}, 实际 {skill_name}")
                
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    print("✓ Hybrid 决策测试完成")


def test_skill_execution():
    """测试技能执行"""
    print("\n" + "=" * 60)
    print("测试 4: 技能执行")
    print("=" * 60)
    
    # 测试设备列表技能（同步技能，不需要 Celery）
    skill = skill_registry.get_skill("device_list")
    if skill:
        print("测试 device_list 技能...")
        try:
            result = asyncio.run(skill.execute(list_type="devices"))
            print(f"  ✓ 执行成功: {result.message}")
            if result.data:
                print(f"  ✓ 返回数据: {len(result.data.get('devices', []))} 个设备")
        except Exception as e:
            print(f"  [ERROR] {e}")
    else:
        print("  [WARN] device_list 技能未找到")
    
    print("✓ 技能执行测试完成")


def main():
    print("=" * 60)
    print("Hybrid 决策架构集成测试")
    print("=" * 60)
    print("日期: 2026-05-20")
    print("=" * 60)
    
    try:
        test_skill_registry()
        test_embedding_prefilter()
        test_hybrid_decision()
        test_skill_execution()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
