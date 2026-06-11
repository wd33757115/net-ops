# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""解析聊天界面粘贴的 CLI 命令与原始输出。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 设备提示符 + 命令，如 <SW>display fan 或 SW>display fan 或 SW#show version
_PROMPT_CMD_LINE = re.compile(
    r"^\s*(?:<(?P<host1>[^>]+)>|(?P<host2>[\w.-]+)[>#])\s*(?P<command>.+?)\s*$",
    re.IGNORECASE,
)
# 行内嵌套：生成模板，<SW>display fan
_EMBEDDED_PROMPT_CMD = re.compile(
    r"(?:<(?P<host1>[^>]+)>|(?P<host2>[\w.-]+)[>#])\s*(?P<command>(?:display|show|get|dis)\s+\S+(?:\s+\S+)*)",
    re.IGNORECASE,
)
# 单独一行的命令（无提示符）
_PLAIN_CMD_LINE = re.compile(
    r"^(?P<command>(?:display|show|get|dis)\s+\S+(?:\s+\S+)*)",
    re.IGNORECASE,
)
# 行内嵌套 plain 命令
_PLAIN_CMD_EMBEDDED = re.compile(
    r"(?P<command>(?:display|show|get|dis)\s+\S+(?:\s+\S+)*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DirectInput:
    command: str
    raw_output: str
    device_prompt: str | None = None


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _find_command_block(
    lines: list[str],
    *,
    explicit_command: str | None = None,
) -> tuple[str, int, str | None]:
    """返回 (command, body_start_line_index, device_prompt)。"""
    if explicit_command:
        cmd = explicit_command.strip()
        for i, line in enumerate(lines):
            if cmd.lower() in line.lower():
                return cmd, i + 1, None
        return cmd, 0, None

    if lines:
        first = lines[0].strip()
        m = _PROMPT_CMD_LINE.match(first)
        if m:
            return (
                m.group("command").strip(),
                1,
                m.group("host1") or m.group("host2"),
            )
        m2 = _PLAIN_CMD_LINE.match(first)
        if m2:
            return m2.group("command").strip(), 1, None

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = _PROMPT_CMD_LINE.match(stripped)
        if m:
            return (
                m.group("command").strip(),
                i + 1,
                m.group("host1") or m.group("host2"),
            )
        m2 = _PLAIN_CMD_LINE.match(stripped)
        if m2:
            return m2.group("command").strip(), i + 1, None

    for i, line in enumerate(lines):
        m = _EMBEDDED_PROMPT_CMD.search(line)
        if m:
            return (
                m.group("command").strip(),
                i + 1,
                m.group("host1") or m.group("host2"),
            )

    for i, line in enumerate(lines):
        m = _PLAIN_CMD_EMBEDDED.search(line)
        if m:
            return m.group("command").strip(), i + 1, None

    return "", 0, None


def parse_chat_cli_block(text: str, *, command: str | None = None) -> DirectInput:
    """
    从用户粘贴文本提取 command 与 CLI 输出体。

    支持格式:
    1) <Host>display fan\\n Slot 1: ...
    2) display fan\\n Slot 1: ...
    3) 命令与输出分多段（首行命令，其余为输出）
    """
    normalized = _normalize_text(text)
    if not normalized:
        raise ValueError("输入为空，请粘贴设备命令及 CLI 输出")

    lines = normalized.split("\n")
    parsed_command, body_start, device_prompt = _find_command_block(
        lines,
        explicit_command=(command or "").strip() or None,
    )

    if not parsed_command:
        raise ValueError("未能识别命令，请在输入中包含如 display fan，或通过 command 参数传入")

    raw_output = "\n".join(lines[body_start:]).strip()
    if not raw_output:
        raise ValueError("缺少 CLI 输出内容，请在命令下方粘贴设备回显")

    return DirectInput(command=parsed_command, raw_output=raw_output, device_prompt=device_prompt)


def extract_direct_input(params: dict) -> DirectInput | None:
    """从 Skill 参数中解析直输模式；无有效 CLI 时返回 None（可回退 SQLite 扫描）。"""
    explicit_cli = params.get("raw_output") or params.get("cli_output")
    text = (
        explicit_cli
        or params.get("user_input")
        or params.get("user_query")
        or params.get("query")
    )
    if not text or not str(text).strip():
        return None
    explicit_cmd = params.get("command")
    try:
        return parse_chat_cli_block(str(text), command=str(explicit_cmd) if explicit_cmd else None)
    except ValueError:
        # 仅意图话术（如「生成 textfsm 模板」）无 CLI → 回退数据库模式
        if explicit_cli:
            raise
        return None


def _hint_source_text(params: dict) -> str:
    return str(
        params.get("user_query")
        or params.get("query")
        or params.get("user_input")
        or params.get("raw_output")
        or params.get("cli_output")
        or ""
    )


def infer_vendor_model(
    params: dict,
    direct: DirectInput,
    *,
    known_devices: list[str] | None = None,
) -> tuple[str, str]:
    """直输模式 vendor/model：显式参数 → LLM 语义理解 → 命令兜底推断。"""
    vendor = (params.get("vendor") or "").strip()
    model = (params.get("model") or "").strip()

    use_semantic = params.get("use_semantic_extraction", True) is not False
    if (not vendor or not model) and use_semantic:
        from semantic_extract import extract_device_context

        hint_text = _hint_source_text(params)
        if hint_text.strip():
            sv, sm = extract_device_context(
                hint_text,
                known_devices=known_devices,
                command=direct.command,
            )
            if not vendor and sv:
                vendor = sv
            if not model and sm:
                model = sm

    if not vendor:
        cmd_lower = direct.command.lower()
        if cmd_lower.startswith(("display ", "dis ")):
            vendor = "Huawei"
        elif cmd_lower.startswith("show "):
            vendor = "Cisco"
        else:
            vendor = "Generic"

    if not model:
        model = (params.get("device_model") or "Generic").strip()

    return vendor, model
