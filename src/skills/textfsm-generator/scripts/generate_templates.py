# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""TextFSM 模板资产生成主流程。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config_loader import (
    load_categories,
    load_command_mapping,
    list_device_profiles,
    required_fields_for_category,
    resolve_category,
)
from db_reader import TemplateCandidate, discover_missing_template_candidates
from input_parser import extract_direct_input, infer_vendor_model
from llm_generator import generate_template_text
from report_generator import GenerationReport, save_report, save_summary
from template_validator import strip_llm_template, validate_template

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS = SKILL_ROOT / "reports"


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def cmd_to_template_filename(command: str) -> str:
    return command.strip().lower().replace(" ", "_") + ".textfsm"


def model_to_dirname(model: str) -> str:
    """与 device-patrol 的 model.replace(' ', '_') 保持一致。"""
    return model.strip().replace(" ", "_")


def resolve_template_path(templates_dir: Path, model: str, command: str) -> Path:
    return templates_dir / model_to_dirname(model) / cmd_to_template_filename(command)


def _build_summary_message(reports: list[GenerationReport], *, mode: str) -> str:
    if not reports:
        if mode == "direct":
            return "未能处理输入，请检查命令与 CLI 输出是否完整"
        return "未发现需要生成模板的记录（SQLite 中无缺失结构化数据的条目）"

    lines: list[str] = []
    for r in reports:
        if r.parsed_records:
            lines.append(f"**{r.command}** — 解析 {len(r.parsed_records)} 条记录：")
            for rec in r.parsed_records:
                parts = ", ".join(f"{k}={v}" for k, v in rec.items())
                lines.append(f"- {parts}")
        elif r.template_generated:
            lines.append(f"**{r.command}** — 模板已生成 ({r.record_count} 条记录)")
        elif r.skipped_reason:
            lines.append(f"**{r.command}** — 跳过: {r.skipped_reason}")
        else:
            lines.append(f"**{r.command}** — 生成失败")

    ok = sum(1 for r in reports if r.template_generated or r.parsed_records)
    prefix = "直输模式" if mode == "direct" else "数据库模式"
    return f"{prefix}完成 ({ok}/{len(reports)}):\n" + "\n".join(lines)


def generate_templates(params: dict[str, Any]) -> dict[str, Any]:
    root = project_root()
    patrol_db = Path(params.get("patrol_db") or root / "db" / "patrol.db")
    devices_db = Path(params.get("devices_db") or root / "db" / "devices.db")
    templates_dir = Path(params.get("templates_dir") or root / "templates")
    reports_dir = Path(params.get("reports_dir") or DEFAULT_REPORTS)
    categories_path = Path(params.get("categories_config") or SKILL_ROOT / "config" / "command_categories.yaml")
    mapping_path = Path(params.get("mapping_config") or SKILL_ROOT / "config" / "command_mapping.yaml")
    max_retries = int(params.get("max_retries") or 3)
    dry_run = bool(params.get("dry_run", False))

    categories = load_categories(categories_path)
    mappings = load_command_mapping(mapping_path)

    direct = extract_direct_input(params)
    reports: list[GenerationReport] = []

    if direct:
        vendor, model = infer_vendor_model(
            params,
            direct,
            known_devices=list_device_profiles(mappings),
        )
        if params.get("model"):
            model = str(params["model"]).strip()
        cand = TemplateCandidate(
            vendor=vendor,
            model=model,
            command=direct.command,
            sample_output=direct.raw_output,
            source_table="direct_input",
            device_id=params.get("device_prompt") or direct.device_prompt or "chat-input",
        )
        force = bool(params.get("force_generate", True))
        report = _process_candidate(
            cand,
            categories=categories,
            mappings=mappings,
            templates_dir=templates_dir,
            reports_dir=reports_dir,
            max_retries=max_retries,
            dry_run=dry_run,
            force_overwrite=force,
            explicit_category=params.get("category"),
            mode="direct",
        )
        reports.append(report)
        mode = "direct"
        candidates_count = 1
    else:
        candidates = discover_missing_template_candidates(
            patrol_db,
            devices_db,
            mappings,
            vendor_filter=params.get("vendor"),
            model_filter=params.get("model"),
            command_filter=params.get("command"),
        )
        for cand in candidates:
            reports.append(
                _process_candidate(
                    cand,
                    categories=categories,
                    mappings=mappings,
                    templates_dir=templates_dir,
                    reports_dir=reports_dir,
                    max_retries=max_retries,
                    dry_run=dry_run,
                    force_overwrite=bool(params.get("force_generate", False)),
                    explicit_category=params.get("category"),
                    mode="database",
                )
            )
        mode = "database"
        candidates_count = len(candidates)

    summary_path = save_summary(reports, reports_dir) if reports else None
    success_count = sum(1 for r in reports if r.template_generated)
    all_parsed: list[dict[str, Any]] = []
    for r in reports:
        if r.parsed_records:
            all_parsed.extend(r.parsed_records)

    return {
        "success": True,
        "message": _build_summary_message(reports, mode=mode),
        "mode": mode,
        "total_candidates": candidates_count,
        "success_count": success_count,
        "parsed_records": all_parsed,
        "reports": [r.to_dict() for r in reports],
        "summary_path": str(summary_path) if summary_path else None,
        "templates_dir": str(templates_dir),
    }


def _process_candidate(
    cand: TemplateCandidate,
    *,
    categories: dict,
    mappings: list,
    templates_dir: Path,
    reports_dir: Path,
    max_retries: int,
    dry_run: bool,
    force_overwrite: bool,
    explicit_category: str | None,
    mode: str,
) -> GenerationReport:
    category = resolve_category(
        cand.vendor,
        cand.model,
        cand.command,
        mappings,
        explicit_category=str(explicit_category) if explicit_category else None,
    )
    if not category:
        report = GenerationReport(
            vendor=cand.vendor,
            model=cand.model,
            command=cand.command,
            category="",
            template_generated=False,
            compile_success=False,
            record_count=0,
            field_coverage=0,
            validation_score=0,
            retry_count=0,
            skipped_reason="无法解析 category，请配置 command_mapping 或传入 category 参数",
            mode=mode,
        )
        save_report(report, reports_dir)
        return report

    required_fields = required_fields_for_category(category, categories)
    if not required_fields:
        report = GenerationReport(
            vendor=cand.vendor,
            model=cand.model,
            command=cand.command,
            category=category,
            template_generated=False,
            compile_success=False,
            record_count=0,
            field_coverage=0,
            validation_score=0,
            retry_count=0,
            skipped_reason=f"command_categories 缺少类别 {category}",
            mode=mode,
        )
        save_report(report, reports_dir)
        return report

    template_path = resolve_template_path(templates_dir, cand.model, cand.command)
    if template_path.is_file() and not force_overwrite:
        # 已有模板：仍尝试解析并返回结构化结果（便于聊天展示）
        existing = template_path.read_text(encoding="utf-8")
        validation = validate_template(
            existing,
            cand.sample_output,
            required_fields,
            categories[category].validators,
        )
        report = GenerationReport(
            vendor=cand.vendor,
            model=cand.model,
            command=cand.command,
            category=category,
            template_generated=False,
            compile_success=validation.compile_success,
            record_count=validation.record_count,
            field_coverage=validation.field_coverage,
            validation_score=validation.validation_score,
            retry_count=0,
            template_path=str(template_path),
            skipped_reason="模板文件已存在（已用现有模板解析）",
            parsed_records=validation.records or None,
            mode=mode,
        )
        save_report(report, reports_dir)
        return report

    validators = categories[category].validators
    template_text = ""
    validation = None
    retry_count = 0

    for attempt in range(max_retries + 1):
        if attempt == 0:
            raw = generate_template_text(
                vendor=cand.vendor,
                model=cand.model,
                command=cand.command,
                cli_output=cand.sample_output,
                required_fields=required_fields,
            )
        else:
            retry_count = attempt
            raw = generate_template_text(
                vendor=cand.vendor,
                model=cand.model,
                command=cand.command,
                cli_output=cand.sample_output,
                required_fields=required_fields,
                previous_template=template_text,
                validation_errors=validation.errors if validation else [],
                missing_fields=validation.missing_fields if validation else [],
                value_errors=validation.value_errors if validation else [],
            )

        template_text = strip_llm_template(raw)
        validation = validate_template(
            template_text,
            cand.sample_output,
            required_fields,
            validators,
        )
        if validation.is_valid:
            break

    parsed = validation.records if validation else []

    if validation and validation.is_valid and not dry_run:
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(template_text, encoding="utf-8")
        generated = True
        saved_path = str(template_path)
    elif validation and validation.is_valid and dry_run:
        generated = False
        saved_path = str(template_path)
    else:
        generated = False
        saved_path = None

    report = GenerationReport(
        vendor=cand.vendor,
        model=cand.model,
        command=cand.command,
        category=category,
        template_generated=generated,
        compile_success=bool(validation and validation.compile_success),
        record_count=validation.record_count if validation else 0,
        field_coverage=validation.field_coverage if validation else 0,
        validation_score=validation.validation_score if validation else 0,
        retry_count=retry_count,
        template_path=saved_path,
        parsed_records=parsed or None,
        errors=(validation.errors if validation else ["验证未执行"]),
        skipped_reason="dry_run" if (validation and validation.is_valid and dry_run) else None,
        mode=mode,
    )
    save_report(report, reports_dir)
    return report
