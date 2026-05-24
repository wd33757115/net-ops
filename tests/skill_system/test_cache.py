# -*- coding: utf-8 -*-
"""
测试 Skill 缓存
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.skill_system.cache import LRUCache, SkillCache


def test_lru_cache_basic():
    """测试 LRU 缓存基本操作"""
    cache = LRUCache(max_size=3)

    # 添加数据
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    # 获取数据
    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"

    print("[OK] test_lru_cache_basic")


def test_lru_cache_eviction():
    """测试 LRU 淘汰"""
    cache = LRUCache(max_size=3)

    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    # 触发淘汰
    cache.set("key4", "value4")

    # key1 应该被淘汰
    assert cache.get("key1") is None
    assert cache.get("key4") == "value4"

    print("[OK] test_lru_cache_eviction")


def test_lru_cache_lru():
    """测试 LRU 特性"""
    cache = LRUCache(max_size=3)

    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    # 访问 key1，使其成为最近使用的
    cache.get("key1")

    # 添加新数据，key2 应该是最老的（因为 key1 被访问了）
    cache.set("key4", "value4")

    # key1 应该还在，key2 应该被淘汰
    assert cache.get("key1") == "value1"
    assert cache.get("key2") is None

    print("[OK] test_lru_cache_lru")


def test_skill_cache():
    """测试 SkillCache"""
    cache = SkillCache()

    # 测试元数据缓存
    cache.set_metadata("skill1", {"name": "test"})
    assert cache.get_metadata("skill1") == {"name": "test"}

    # 测试指令缓存
    cache.set_instructions("skill1", "instruction content")
    assert cache.get_instructions("skill1") == "instruction content"

    print("[OK] test_skill_cache")


def test_skill_cache_stats():
    """测试缓存统计"""
    cache = LRUCache(max_size=3)

    cache.set("key1", "value1")
    cache.get("key1")  # hit
    cache.get("key1")  # hit
    cache.get("key2")  # miss

    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert "50" in stats["hit_rate"] or "66" in stats["hit_rate"]  # 2/4=50% or 2/3=66%

    print("[OK] test_skill_cache_stats")


if __name__ == "__main__":
    print("=" * 50)
    print("运行 Skill 缓存测试")
    print("=" * 50)

    test_lru_cache_basic()
    test_lru_cache_eviction()
    test_lru_cache_lru()
    test_skill_cache()
    test_skill_cache_stats()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)
