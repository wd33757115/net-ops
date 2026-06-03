# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""直接测试公文写作技能"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 PATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))
sys.stdout.reconfigure(encoding='utf-8')

async def test_doc():
    # 导入技能
    from src.skills.examples.official_document_writing_skill import register_skill
    from src.skills.registry import skill_registry

    # 注册技能
    register_skill()
    skill = skill_registry.get_skill("official_document_writing")

    if skill:
        print(f"✅ 技能已注册: {skill.name}")

        # 执行技能
        result = await skill.execute(
            document_type="请示",
            action="write",
            user_query="帮我写一份请示，向信息中心申请采购新的服务器"
        )

        print(f"执行成功: {result.success}")
        print(f"消息: {result.message}")
        print(f"下载链接: {result.download_url}")

        if result.data:
            print(f"文档内容预览: {result.data.get('document_content', '')[:200]}...")

    else:
        print("❌ 技能未找到")

asyncio.run(test_doc())
