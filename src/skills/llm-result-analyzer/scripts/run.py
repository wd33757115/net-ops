#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""LLM 结果分析 Skill：读取上游 Skill/Workflow 步骤 JSON，调用 LLM 生成结构化分析报告。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from llm_analyze import analyze_with_llm, build_input_summary, load_upstream_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM 上游结果分析 Skill")
    parser.add_argument("--params", required=True, help="params.json 路径")
    parser.add_argument("-o", "--output", help="可选：将分析报告 Markdown 写入文件")
    args = parser.parse_args()

    with open(args.params, encoding="utf-8-sig") as f:
        params = json.load(f)

    try:
        upstream = load_upstream_payload(params)
        summary = build_input_summary(upstream, params)
        analysis = analyze_with_llm(
            user_query=params.get("analysis_prompt") or params.get("user_query") or "",
            upstream_summary=summary,
            analysis_focus=params.get("analysis_focus") or "summary",
            ticket_id=params.get("ticket_id"),
        )
        result: dict[str, Any] = {
            "success": True,
            "message": "LLM 分析完成",
            "analysis": analysis.get("text", ""),
            "analysis_json": analysis.get("structured"),
            "upstream_skill": params.get("upstream_skill") or params.get("source_step"),
            "model": analysis.get("model"),
        }
        if args.output:
            Path(args.output).write_text(result["analysis"], encoding="utf-8")
            result["report_filename"] = Path(args.output).name

        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        err = {"success": False, "error": str(exc), "message": str(exc)}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
