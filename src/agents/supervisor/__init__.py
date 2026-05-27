"""Supervisor Agent 图构建入口（v2 为唯一运行时入口）。"""

from src.agents.supervisor.graph_v2 import (
    build_supervisor_graph_v2,
    compiled_graph_v2,
    get_supervisor_graph_v2,
)

# 兼容旧 import 名称
build_supervisor_graph = build_supervisor_graph_v2
compiled_graph = compiled_graph_v2
get_supervisor_graph = get_supervisor_graph_v2

__all__ = [
    "build_supervisor_graph",
    "build_supervisor_graph_v2",
    "compiled_graph",
    "compiled_graph_v2",
    "get_supervisor_graph",
    "get_supervisor_graph_v2",
]
