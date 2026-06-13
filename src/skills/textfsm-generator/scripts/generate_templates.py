# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""TextFSM parser asset generation for direct, database, and directory inputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config_loader import (
    CategorySpec,
    list_device_profiles,
    load_categories,
    load_command_aliases,
    load_command_mapping,
    load_device_signatures,
    normalize_command,
    resolve_category,
)
from db_reader import TemplateCandidate, discover_missing_template_candidates
from directory_reader import DirectoryCandidate, TemplateSample, discover_directory_candidates
from input_parser import extract_direct_input, infer_vendor_model
from llm_generator import generate_template_text
from report_generator import GenerationReport, save_report, save_summary
from template_validator import ValidationResult, strip_llm_template, validate_template

from src.core.patrol.textfsm_assets import (
    SHARED_TEXTFSM_ROOT,
    atomic_write_text,
    command_template_name,
    remove_manifest_entry,
    safe_slug,
    template_path,
    upsert_manifest_entry,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS = SKILL_ROOT / "reports"
PARSER_VERSION = "1.0.0"


@dataclass(frozen=True)
class Candidate:
    vendor: str
    model: str
    family: str | None
    command: str
    category: str | None
    samples: tuple[TemplateSample, ...]
    confidence: float | None = None
    evidence_command: str | None = None
    evidence_text: str | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def cmd_to_template_filename(command: str) -> str:
    return command_template_name(command)


def model_to_dirname(model: str) -> str:
    return safe_slug(model)


def resolve_template_path(templates_dir: Path, model: str, command: str) -> Path:
    return template_path(templates_dir, model, command)


def _direct_candidate(params: dict[str, Any], mappings: list[Any]) -> Candidate | None:
    direct = extract_direct_input(params)
    if not direct:
        return None
    vendor, model = infer_vendor_model(
        params,
        direct,
        known_devices=list_device_profiles(mappings),
    )
    command = normalize_command(direct.command)
    return Candidate(
        vendor=vendor,
        model=model,
        family=None,
        command=command,
        category=str(params.get("category") or "").strip() or None,
        samples=(
            TemplateSample(
                file_path="direct_input",
                device_id=direct.device_prompt or "chat-input",
                command=command,
                output=direct.raw_output,
            ),
        ),
        confidence=1.0 if params.get("vendor") and params.get("model") else None,
    )


def _database_candidates(items: list[TemplateCandidate]) -> list[Candidate]:
    return [
        Candidate(
            vendor=item.vendor,
            model=item.model,
            family=None,
            command=normalize_command(item.command),
            category=None,
            samples=(
                TemplateSample(
                    file_path=item.source_table,
                    device_id=item.device_id,
                    command=normalize_command(item.command),
                    output=item.sample_output,
                ),
            ),
        )
        for item in items
    ]


def _directory_candidates(items: tuple[DirectoryCandidate, ...]) -> list[Candidate]:
    return [
        Candidate(
            vendor=item.vendor,
            model=item.model,
            family=item.family,
            command=item.command,
            category=item.category,
            samples=item.samples,
            confidence=item.confidence,
            evidence_command=item.evidence_command,
            evidence_text=item.evidence_text,
        )
        for item in items
    ]


def _prompt_samples(samples: tuple[TemplateSample, ...], limit: int) -> str:
    selected = samples[: max(1, limit)]
    parts = [
        f"===== sample {index + 1}: {sample.device_id} / {sample.file_path} =====\n"
        f"{sample.output}"
        for index, sample in enumerate(selected)
    ]
    return "\n\n".join(parts)


def _validate_samples(
    template_text: str,
    samples: tuple[TemplateSample, ...],
    spec: CategorySpec,
) -> tuple[list[ValidationResult], list[dict[str, Any]]]:
    validations: list[ValidationResult] = []
    details: list[dict[str, Any]] = []
    for sample in samples:
        result = validate_template(
            template_text,
            sample.output,
            spec.required_fields,
            spec.validators,
            allow_empty=spec.allow_empty,
            empty_patterns=spec.empty_patterns,
        )
        validations.append(result)
        details.append(
            {
                "file_path": sample.file_path,
                "device_id": sample.device_id,
                "valid": result.is_valid,
                "record_count": result.record_count,
                "empty_accepted": result.empty_accepted,
                "field_coverage": result.field_coverage,
                "validation_score": result.validation_score,
                "errors": result.errors,
            }
        )
    return validations, details


def _manifest_entry(
    *,
    candidate: Candidate,
    category: str,
    spec: CategorySpec,
    target: Path,
    templates_dir: Path,
    template_text: str,
    pass_rate: float,
) -> dict[str, Any]:
    return {
        "vendor": candidate.vendor,
        "model": candidate.model,
        "family": candidate.family,
        "command": candidate.command,
        "category": category,
        "entity_type": spec.entity_type,
        "primary_keys": spec.primary_keys,
        "required_fields": spec.required_fields,
        "optional_fields": spec.optional_fields,
        "parser_version": PARSER_VERSION,
        "template_path": str(target.relative_to(templates_dir)),
        "sha256": hashlib.sha256(template_text.encode("utf-8")).hexdigest(),
        "sample_count": len(candidate.samples),
        "validation_pass_rate": pass_rate,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def _report_failure(
    candidate: Candidate,
    *,
    mode: str,
    reason: str,
    reports_dir: Path,
) -> GenerationReport:
    report = GenerationReport(
        vendor=candidate.vendor,
        model=candidate.model,
        family=candidate.family,
        command=candidate.command,
        category=candidate.category or "",
        template_generated=False,
        compile_success=False,
        record_count=0,
        field_coverage=0,
        validation_score=0,
        retry_count=0,
        skipped_reason=reason,
        mode=mode,
        sample_count=len(candidate.samples),
        confidence=candidate.confidence,
        evidence_command=candidate.evidence_command,
        evidence_text=candidate.evidence_text,
    )
    save_report(report, reports_dir)
    return report


def _process_candidate(
    candidate: Candidate,
    *,
    categories: dict[str, CategorySpec],
    mappings: list[Any],
    templates_dir: Path,
    reports_dir: Path,
    max_retries: int,
    dry_run: bool,
    publish: bool,
    force_overwrite: bool,
    minimum_pass_rate: float,
    max_samples_per_prompt: int,
    explicit_category: str | None,
    mode: str,
) -> GenerationReport:
    category = candidate.category or resolve_category(
        candidate.vendor,
        candidate.model,
        candidate.command,
        mappings,
        explicit_category=explicit_category,
    )
    if not category:
        return _report_failure(
            candidate,
            mode=mode,
            reason="command_not_configured",
            reports_dir=reports_dir,
        )
    spec = categories.get(category)
    if not spec or not spec.required_fields:
        return _report_failure(
            candidate,
            mode=mode,
            reason=f"category_not_configured:{category}",
            reports_dir=reports_dir,
        )

    target = resolve_template_path(templates_dir, candidate.model, candidate.command)
    template_text = ""
    retry_count = 0
    validations: list[ValidationResult] = []
    sample_results: list[dict[str, Any]] = []
    target_existed = target.is_file()
    previous_asset_valid = False

    if target_existed:
        template_text = target.read_text(encoding="utf-8")
        validations, sample_results = _validate_samples(template_text, candidate.samples, spec)
        existing_passed = sum(result.is_valid for result in validations)
        existing_rate = existing_passed / len(validations) if validations else 0.0
        previous_asset_valid = bool(validations) and existing_rate >= minimum_pass_rate
    if target_existed and previous_asset_valid and not force_overwrite:
        skipped_reason = "template_exists"
    else:
        skipped_reason = None
        previous_errors: list[str] = []
        missing_fields: list[str] = []
        value_errors: list[str] = []
        for attempt in range(max_retries + 1):
            retry_count = attempt
            raw = generate_template_text(
                vendor=candidate.vendor,
                model=candidate.model,
                command=candidate.command,
                cli_output=_prompt_samples(candidate.samples, max_samples_per_prompt),
                required_fields=spec.required_fields,
                optional_fields=spec.optional_fields,
                previous_template=template_text or None,
                validation_errors=previous_errors,
                missing_fields=missing_fields,
                value_errors=value_errors,
            )
            template_text = strip_llm_template(raw)
            validations, sample_results = _validate_samples(
                template_text, candidate.samples, spec
            )
            passed = sum(result.is_valid for result in validations)
            pass_rate = passed / len(validations) if validations else 0.0
            if pass_rate >= minimum_pass_rate:
                break
            failed = [result for result in validations if not result.is_valid]
            previous_errors = [
                error for result in failed for error in result.errors
            ][:30]
            missing_fields = sorted(
                {field for result in failed for field in result.missing_fields}
            )
            value_errors = [
                error for result in failed for error in result.value_errors
            ][:30]

    passed_samples = sum(result.is_valid for result in validations)
    pass_rate = passed_samples / len(validations) if validations else 0.0
    accepted = bool(validations) and pass_rate >= minimum_pass_rate
    generated = False
    if (
        accepted
        and publish
        and not dry_run
        and (force_overwrite or not target.is_file() or not previous_asset_valid)
    ):
        atomic_write_text(target, template_text)
        generated = True
        upsert_manifest_entry(
            _manifest_entry(
                candidate=candidate,
                category=category,
                spec=spec,
                target=target,
                templates_dir=templates_dir,
                template_text=template_text,
                pass_rate=pass_rate,
            ),
            root=templates_dir,
        )
    elif accepted and publish and not dry_run and target.is_file():
        upsert_manifest_entry(
            _manifest_entry(
                candidate=candidate,
                category=category,
                spec=spec,
                target=target,
                templates_dir=templates_dir,
                template_text=template_text,
                pass_rate=pass_rate,
            ),
            root=templates_dir,
        )
    elif target_existed and not previous_asset_valid and target.is_file():
        rejected_dir = reports_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        rejected = rejected_dir / (
            f"{safe_slug(candidate.vendor)}_{safe_slug(candidate.model)}_"
            f"{command_template_name(candidate.command)}"
        )
        target.replace(rejected)
        remove_manifest_entry(
            vendor=candidate.vendor,
            model=candidate.model,
            command=candidate.command,
            root=templates_dir,
        )

    all_records = [
        record for result in validations if result.is_valid for record in result.records
    ]
    errors = [
        error for result in validations if not result.is_valid for error in result.errors
    ]
    report = GenerationReport(
        vendor=candidate.vendor,
        model=candidate.model,
        family=candidate.family,
        command=candidate.command,
        category=category,
        entity_type=spec.entity_type,
        primary_keys=spec.primary_keys,
        template_generated=generated,
        compile_success=all(result.compile_success for result in validations),
        record_count=sum(result.record_count for result in validations),
        field_coverage=min(
            (result.field_coverage for result in validations), default=0
        ),
        validation_score=min(
            (result.validation_score for result in validations), default=0
        ),
        retry_count=retry_count,
        template_path=str(target) if accepted else None,
        skipped_reason=(
            skipped_reason
            if skipped_reason
            else "dry_run"
            if accepted and (dry_run or not publish)
            else "sample_pass_rate_below_threshold"
            if not accepted
            else None
        ),
        errors=errors or None,
        parsed_records=all_records or None,
        mode=mode,
        sample_count=len(candidate.samples),
        passed_samples=passed_samples,
        validation_pass_rate=pass_rate,
        sample_results=sample_results,
        confidence=candidate.confidence,
        evidence_command=candidate.evidence_command,
        evidence_text=candidate.evidence_text,
    )
    save_report(report, reports_dir)
    return report


def generate_templates(params: dict[str, Any]) -> dict[str, Any]:
    root = project_root()
    templates_dir = Path(params.get("templates_dir") or SHARED_TEXTFSM_ROOT)
    reports_dir = Path(params.get("reports_dir") or DEFAULT_REPORTS)
    categories = load_categories(
        Path(params.get("categories_config") or SKILL_ROOT / "config" / "command_categories.yaml")
    )
    mappings = load_command_mapping(
        Path(params.get("mapping_config") or SKILL_ROOT / "config" / "command_mapping.yaml")
    )
    aliases = load_command_aliases(
        Path(params.get("command_aliases_config") or SKILL_ROOT / "config" / "command_aliases.yaml")
    )
    reports: list[GenerationReport] = []
    discovery_metadata: dict[str, Any] = {}

    direct = _direct_candidate(params, mappings)
    if params.get("source_path"):
        discovery = discover_directory_candidates(
            params["source_path"],
            mappings=mappings,
            signatures=load_device_signatures(
                Path(
                    params.get("device_signatures_config")
                    or SKILL_ROOT / "config" / "device_signatures.yaml"
                )
            ),
            aliases=aliases,
            recursive=bool(params.get("recursive", True)),
            vendor=params.get("vendor"),
            model=params.get("model"),
            command_filter=params.get("command"),
        )
        candidates = _directory_candidates(discovery.candidates)
        mode = "directory"
        discovery_metadata = {
            "files_scanned": discovery.files_scanned,
            "devices_detected": discovery.devices_detected,
            "device_profiles": list(discovery.device_profiles),
            "skipped_commands": list(discovery.skipped_commands),
            "unresolved_files": list(discovery.unresolved_files),
        }
    elif direct:
        candidates = [direct]
        mode = "direct"
    else:
        database_items = discover_missing_template_candidates(
            Path(params.get("patrol_db") or root / "db" / "patrol.db"),
            Path(params.get("devices_db") or root / "db" / "devices.db"),
            mappings,
            vendor_filter=params.get("vendor"),
            model_filter=params.get("model"),
            command_filter=params.get("command"),
        )
        candidates = _database_candidates(database_items)
        mode = "database"

    for candidate in candidates:
        reports.append(
            _process_candidate(
                candidate,
                categories=categories,
                mappings=mappings,
                templates_dir=templates_dir,
                reports_dir=reports_dir,
                max_retries=int(params.get("max_retries", 3)),
                dry_run=bool(params.get("dry_run", False)),
                publish=bool(params.get("publish", True)),
                force_overwrite=bool(
                    params.get("force_generate", mode == "direct")
                ),
                minimum_pass_rate=float(params.get("minimum_sample_pass_rate", 1.0)),
                max_samples_per_prompt=int(params.get("max_samples_per_prompt", 3)),
                explicit_category=str(params.get("category") or "").strip() or None,
                mode=mode,
            )
        )

    summary_path = save_summary(
        reports,
        reports_dir,
        metadata={"mode": mode, **discovery_metadata},
    )
    generated = [report for report in reports if report.template_generated]
    passed = sum(report.passed_samples for report in reports)
    samples = sum(report.sample_count for report in reports)
    return {
        "success": not discovery_metadata.get("unresolved_files"),
        "message": (
            f"{mode} mode processed {len(reports)} candidate groups; "
            f"published {len(generated)} templates"
            + (
                f"; commands: {', '.join(report.command for report in reports)}"
                if reports
                else ""
            )
        ),
        "mode": mode,
        "total_candidates": len(candidates),
        "candidate_groups": len(candidates),
        "success_count": len(generated),
        "generated_templates": [
            report.template_path for report in generated if report.template_path
        ],
        "validation_pass_rate": passed / samples if samples else 0.0,
        "parsed_records": [
            record for report in reports for record in (report.parsed_records or [])
        ],
        "reports": [report.to_dict() for report in reports],
        "summary_path": str(summary_path),
        "shared_templates_dir": str(templates_dir),
        **discovery_metadata,
    }
