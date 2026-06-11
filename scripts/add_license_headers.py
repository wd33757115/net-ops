#!/usr/bin/env python3
"""为项目源码批量添加 Apache-2.0 SPDX 文件头（幂等）。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPYRIGHT = "2026 wangdong <wangdong5919@163.com>"
SPDX_ID = "Apache-2.0"
MARKER = "SPDX-License-Identifier"

SKIP_DIR_NAMES = {
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".git",
    "chroma_db",
    "vectorstore",
    ".runtime",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "htmlcov",
    ".next",
    "site-packages",
}

# 按扩展名选择注释风格：(prefix, suffix)
COMMENT_STYLES: dict[str, tuple[str, str]] = {
    ".py": ("# ", ""),
    ".ps1": ("# ", ""),
    ".sh": ("# ", ""),
    ".yaml": ("# ", ""),
    ".yml": ("# ", ""),
    ".css": ("/* ", " */"),
    ".ts": ("// ", ""),
    ".tsx": ("// ", ""),
    ".js": ("// ", ""),
    ".jsx": ("// ", ""),
    ".html": ("<!-- ", " -->"),
}

# 扫描根目录
SCAN_ROOTS = ["src", "web", "scripts", "tests", "deployment", "docs", "schemas"]
ROOT_FILES = [
    "README.md",
    "web/README.md",
    ".env.example",
    "Makefile",
    "deployment/Dockerfile.fastapi",
    "deployment/Dockerfile.django",
    "deployment/Dockerfile.react",
]

SKIP_FILE_NAMES = {
    "LICENSE",
    "package-lock.json",
    "poetry.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
}


def _has_license(text: str) -> bool:
    return MARKER in text or "Licensed under the Apache License" in text


def _md_header() -> str:
    return (
        f"<!-- SPDX-FileCopyrightText: {COPYRIGHT} -->\n"
        f"<!-- SPDX-License-Identifier: {SPDX_ID} -->\n\n"
    )


def _comment_header(prefix: str, suffix: str) -> str:
    line1 = f"{prefix}SPDX-FileCopyrightText: {COPYRIGHT}{suffix}\n"
    line2 = f"{prefix}SPDX-License-Identifier: {SPDX_ID}{suffix}\n"
    return line1 + line2 + "\n"


def _insert_python(content: str, header: str) -> str:
    lines = content.splitlines(keepends=True)
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith("#!") or re.match(r"^#\s*-\*-.*coding", stripped):
            idx += 1
            continue
        if stripped == "":
            idx += 1
            continue
        break
    return "".join(lines[:idx]) + header + "".join(lines[idx:])


def _insert_html(content: str, header: str) -> str:
    """HTML：DOCTYPE 之后插入。"""
    lower = content.lower()
    if lower.startswith("<!doctype"):
        end = content.find(">", content.lower().find("<!doctype")) + 1
        rest = content[end:]
        if rest.startswith("\r\n"):
            end += 2
        elif rest.startswith("\n"):
            end += 1
        return content[:end] + "\n" + header + content[end:]
    return header + content


def add_header(path: Path) -> bool:
    if path.name in SKIP_FILE_NAMES:
        return False
    if path.name == "LICENSE" or path.name.endswith(".lock"):
        return False
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return False

    suffix = path.suffix.lower()
    if path.name == "Dockerfile" or path.name.startswith("Dockerfile."):
        suffix = ".sh"  # shell-style comments

    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    if _has_license(raw):
        return False

    if suffix == ".md":
        stripped = raw.lstrip("\ufeff")
        # 带 YAML frontmatter 的 md（如 SKILL.md）：header 放末尾，避免破坏 --- 解析
        if stripped.lstrip().startswith("---"):
            new_content = stripped.rstrip() + "\n\n" + _md_header().rstrip() + "\n"
        else:
            new_content = _md_header() + stripped
    elif suffix in COMMENT_STYLES:
        prefix, sfx = COMMENT_STYLES[suffix]
        header = _comment_header(prefix, sfx)
        if suffix == ".py":
            new_content = _insert_python(raw, header)
        elif suffix == ".html":
            new_content = _insert_html(raw, header)
        else:
            new_content = header + raw.lstrip("\ufeff")
    else:
        return False

    if new_content != raw:
        path.write_text(new_content, encoding="utf-8", newline="\n")
        return True
    return False


def collect_files() -> list[Path]:
    files: set[Path] = set()
    for rel in SCAN_ROOTS:
        base = ROOT / rel
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() in COMMENT_STYLES or p.suffix.lower() == ".md":
                files.add(p)
            elif p.name == "Dockerfile" or p.name.startswith("Dockerfile."):
                files.add(p)
    for rel in ROOT_FILES:
        p = ROOT / rel
        if p.is_file():
            files.add(p)
    return sorted(files)


def main() -> None:
    updated = 0
    skipped = 0
    for path in collect_files():
        if add_header(path):
            updated += 1
            print(f"updated: {path.relative_to(ROOT)}")
        else:
            skipped += 1
    print(f"\nDone. updated={updated}, skipped={skipped}")


if __name__ == "__main__":
    main()
