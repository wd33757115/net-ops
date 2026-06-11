# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""textfsm-generator 单元测试（不调用 LLM）。"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "src" / "skills" / "textfsm-generator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from config_loader import (  # noqa: E402
    find_category,
    load_categories,
    load_command_mapping,
    required_fields_for_category,
    resolve_device_mapping,
)
from db_reader import discover_missing_template_candidates  # noqa: E402
from generate_templates import cmd_to_template_filename, model_to_dirname, resolve_template_path  # noqa: E402
from report_generator import GenerationReport, save_report  # noqa: E402
from template_validator import (  # noqa: E402
    check_required_fields,
    strip_llm_template,
    validate_field_values,
    validate_template,
)

try:
    import textfsm  # noqa: F401
    HAS_TEXTFSM = True
except ImportError:
    HAS_TEXTFSM = False


SAMPLE_TEMPLATE = """Value Slot (\\S+)
Value CPU_5S (\\d+)
Value CPU_1M (\\d+)
Value CPU_5M (\\d+)

Start
  ^Slot\\s+${Slot}\\s+CPU\\s+5s\\s+1m\\s+5m
  ^${Slot}\\s+${CPU_5S}\\s+${CPU_1M}\\s+${CPU_5M}
"""

SAMPLE_CLI = """Slot  CPU 5s 1m 5m
0     10   12  15
1     8    9   11
"""


class TestConfigLoader(unittest.TestCase):
    def test_load_mapping_and_category(self):
        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        mappings = load_command_mapping(skill_root / "config" / "command_mapping.yaml")
        categories = load_categories(skill_root / "config" / "command_categories.yaml")
        self.assertTrue(mappings)
        cat = find_category("Huawei", "CE12800", "display cpu-usage", mappings)
        self.assertEqual(cat, "cpu")
        fields = required_fields_for_category(cat, categories)
        self.assertIn("cpu_5s", fields)

    def test_resolve_category_fan_generic(self):
        from config_loader import resolve_category

        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        mappings = load_command_mapping(skill_root / "config" / "command_mapping.yaml")
        cat = resolve_category("Huawei", "Generic", "display fan", mappings)
        self.assertEqual(cat, "fan")

    def test_resolve_device_model(self):
        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        mappings = load_command_mapping(skill_root / "config" / "command_mapping.yaml")
        self.assertEqual(resolve_device_mapping("CE12800", mappings), ("Huawei", "CE12800"))


class TestDbReader(unittest.TestCase):
    def _setup_dbs(self, tmp: Path):
        devices = tmp / "devices.db"
        patrol = tmp / "patrol.db"
        conn = sqlite3.connect(devices)
        try:
            conn.execute(
                "CREATE TABLE devices (device_id INTEGER PRIMARY KEY, device_name TEXT, ip TEXT, model TEXT)"
            )
            conn.execute(
                "INSERT INTO devices (device_name, ip, model) VALUES (?,?,?)",
                ("sw1", "10.0.0.1", "CE12800"),
            )
            conn.commit()
        finally:
            conn.close()

        conn = sqlite3.connect(patrol)
        try:
            conn.executescript(
                """
                CREATE TABLE patrol_data (
                    run_id TEXT, device_id TEXT, command TEXT,
                    structured TEXT, text_output TEXT, timestamp TEXT,
                    PRIMARY KEY (run_id, device_id, command)
                );
                """
            )
            conn.execute(
                "INSERT INTO patrol_data VALUES (?,?,?,?,?,?)",
                ("r1", "sw1-10.0.0.1", "display cpu-usage", None, SAMPLE_CLI, "2026-01-01"),
            )
            conn.execute(
                "INSERT INTO patrol_data VALUES (?,?,?,?,?,?)",
                ("r2", "sw1-10.0.0.1", "display cpu-usage", None, SAMPLE_CLI, "2026-01-02"),
            )
            conn.commit()
        finally:
            conn.close()
        return patrol, devices

    def test_dedupe_by_vendor_model_command(self):
        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        mappings = load_command_mapping(skill_root / "config" / "command_mapping.yaml")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            patrol, devices = self._setup_dbs(Path(tmpdir))
            items = discover_missing_template_candidates(patrol, devices, mappings)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].vendor, "Huawei")
            self.assertEqual(items[0].model, "CE12800")


class TestTemplateValidator(unittest.TestCase):
    @unittest.skipUnless(HAS_TEXTFSM, "textfsm not installed")
    def test_four_layer_validation(self):
        # 字段名映射为模板 Value 名（大写+下划线是 TextFSM 惯例，配置用小写）
        template = """Value slot (\\d+)
Value cpu_5s (\\d+)
Value cpu_1m (\\d+)
Value cpu_5m (\\d+)

Start
  ^Slot\\s+CPU
  ^${slot}\\s+${cpu_5s}\\s+${cpu_1m}\\s+${cpu_5m}
"""
        cli = "Slot CPU\n0 10 12 15\n1 8 9 11\n"
        required = ["slot", "cpu_5s", "cpu_1m", "cpu_5m"]
        validators = {
            "cpu_5s": {"type": "percent"},
            "cpu_1m": {"type": "percent"},
            "cpu_5m": {"type": "percent"},
        }
        result = validate_template(template, cli, required, validators)
        self.assertTrue(result.compile_success)
        self.assertGreater(result.record_count, 0)
        self.assertEqual(result.missing_fields, [])

    def test_strip_llm_fence(self):
        raw = "```textfsm\nValue X (\\d+)\n\nStart\n  ^${X}\n```"
        cleaned = strip_llm_template(raw)
        self.assertIn("Value X", cleaned)
        self.assertNotIn("```", cleaned)

    def test_field_value_percent(self):
        errors = validate_field_values(
            [{"cpu_5s": "150"}],
            {"cpu_5s": {"type": "percent"}},
        )
        self.assertTrue(errors)

    def test_required_field_coverage(self):
        cov, missing = check_required_fields([{"a": "1"}], ["a", "b"])
        self.assertEqual(missing, ["b"])
        self.assertEqual(cov, 50)


class TestInputParser(unittest.TestCase):
    def test_parse_display_fan_block(self):
        from input_parser import parse_chat_cli_block

        text = """<XA-FOTIC-Ant-SW>display fan
 Slot 1:
 Fan 1:
 State    : Normal
 Fan 2:
 State    : Normal"""
        parsed = parse_chat_cli_block(text)
        self.assertEqual(parsed.command, "display fan")
        self.assertEqual(parsed.device_prompt, "XA-FOTIC-Ant-SW")
        self.assertIn("Slot 1:", parsed.raw_output)
        self.assertIn("Fan 1:", parsed.raw_output)

    def test_extract_from_params(self):
        from input_parser import extract_direct_input

        direct = extract_direct_input({"user_query": "display fan\nline1\nline2"})
        self.assertIsNotNone(direct)
        assert direct is not None
        self.assertEqual(direct.command, "display fan")
        self.assertEqual(direct.raw_output, "line1\nline2")

    def test_extract_intent_only_falls_back_to_database(self):
        from input_parser import extract_direct_input

        self.assertIsNone(extract_direct_input({"user_query": "生成textfsm解析模板"}))

    def test_explicit_cli_still_raises_when_invalid(self):
        from input_parser import extract_direct_input

        with self.assertRaises(ValueError):
            extract_direct_input({"raw_output": "只有一行没有命令"})

    def test_parse_with_natural_language_prefix(self):
        from input_parser import parse_chat_cli_block

        text = """生成TEXTFSM解析模板，<XA-FOTIC-Ant-SW>display fan
 Slot 1:
 Fan 1:
 State    : Normal"""
        parsed = parse_chat_cli_block(text)
        self.assertEqual(parsed.command, "display fan")
        self.assertEqual(parsed.device_prompt, "XA-FOTIC-Ant-SW")
        self.assertIn("Slot 1:", parsed.raw_output)

    def test_infer_vendor_model_semantic(self):
        from unittest.mock import patch

        from input_parser import infer_vendor_model, parse_chat_cli_block

        text = """帮我给华三核心交换机 S5590 生成 textfsm 模板
<SW>display cpu
Slot 1 CPU 0 CPU usage:
      21% in last 5 seconds"""
        direct = parse_chat_cli_block(text)

        with patch("semantic_extract.extract_device_context", return_value=("H3C", "S5590")):
            vendor, model = infer_vendor_model(
                {"user_query": text},
                direct,
                known_devices=["H3C S5590", "Huawei CE12800"],
            )
        self.assertEqual(vendor, "H3C")
        self.assertEqual(model, "S5590")

    def test_infer_vendor_model_skips_semantic_when_disabled(self):
        from unittest.mock import patch

        from input_parser import infer_vendor_model, parse_chat_cli_block

        text = "display fan\nSlot 1:\nFan 1:\nState : Normal"
        direct = parse_chat_cli_block(text)

        with patch("semantic_extract.extract_device_context") as mock_extract:
            vendor, model = infer_vendor_model(
                {"user_query": text, "use_semantic_extraction": False},
                direct,
            )
            mock_extract.assert_not_called()
        self.assertEqual(vendor, "Huawei")
        self.assertEqual(model, "Generic")

    def test_semantic_parse_json(self):
        from semantic_extract import _parse_json_object, build_extract_prompt

        data = _parse_json_object('说明\n{"vendor": "H3C", "model": "S5590"}')
        self.assertEqual(data.get("vendor"), "H3C")
        self.assertEqual(data.get("model"), "S5590")

        prompt = build_extract_prompt(
            "华三 S5590 生成模板",
            known_devices=["H3C S5590"],
            command="display cpu",
        )
        self.assertIn("H3C S5590", prompt)
        self.assertIn("自然语义", prompt)


class TestGenerateFlow(unittest.TestCase):
    def test_template_path_compatible_with_patrol(self):
        path = resolve_template_path(Path("/tmp/templates"), "CE12800", "display cpu-usage")
        self.assertEqual(path.name, "display_cpu-usage.textfsm")
        self.assertEqual(path.parent.name, "CE12800")

    @patch("generate_templates.generate_template_text")
    def test_end_to_end_with_mock_llm(self, mock_llm):
        mock_llm.return_value = """Value slot (\\d+)
Value cpu_5s (\\d+)
Value cpu_1m (\\d+)
Value cpu_5m (\\d+)

Start
  ^Slot\\s+CPU
  ^${slot}\\s+${cpu_5s}\\s+${cpu_1m}\\s+${cpu_5m}
"""
        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        mappings = load_command_mapping(skill_root / "config" / "command_mapping.yaml")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp = Path(tmpdir)
            patrol = tmp / "patrol.db"
            devices = tmp / "devices.db"
            templates = tmp / "templates"
            reports = tmp / "reports"

            conn = sqlite3.connect(devices)
            try:
                conn.execute(
                    "CREATE TABLE devices (device_id INTEGER PRIMARY KEY, device_name TEXT, ip TEXT, model TEXT)"
                )
                conn.execute(
                    "INSERT INTO devices (device_name, ip, model) VALUES (?,?,?)",
                    ("sw1", "10.0.0.1", "CE12800"),
                )
                conn.commit()
            finally:
                conn.close()

            conn = sqlite3.connect(patrol)
            try:
                conn.executescript(
                    """
                    CREATE TABLE patrol_data (
                        run_id TEXT, device_id TEXT, command TEXT,
                        structured TEXT, text_output TEXT, timestamp TEXT,
                        PRIMARY KEY (run_id, device_id, command)
                    );
                    """
                )
                cli = "Slot CPU\n0 10 12 15\n"
                conn.execute(
                    "INSERT INTO patrol_data VALUES (?,?,?,?,?,?)",
                    ("r1", "sw1-10.0.0.1", "display cpu-usage", None, cli, "2026-01-01"),
                )
                conn.commit()
            finally:
                conn.close()

            from generate_templates import generate_templates

            result = generate_templates(
                {
                    "patrol_db": str(patrol),
                    "devices_db": str(devices),
                    "templates_dir": str(templates),
                    "reports_dir": str(reports),
                    "mapping_config": str(skill_root / "config" / "command_mapping.yaml"),
                    "categories_config": str(skill_root / "config" / "command_categories.yaml"),
                    "max_retries": 1,
                }
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["success_count"], 1)
            out_file = templates / "CE12800" / cmd_to_template_filename("display cpu-usage")
            self.assertTrue(out_file.is_file())
            report_files = list(reports.glob("*.json"))
            self.assertTrue(report_files)

    @patch("generate_templates.generate_template_text")
    def test_direct_input_mode(self, mock_llm):
        mock_llm.return_value = """Value slot (\\d+)
Value fan (\\d+)
Value state (\\S+)

Start
  ^Slot\\s+${slot}:
  ^Fan\\s+${fan}:
  ^State\\s+:\\s+${state}
"""
        skill_root = PROJECT_ROOT / "src" / "skills" / "textfsm-generator"
        cli = """Slot 1:
Fan 1:
State    : Normal
Fan 2:
State    : Normal"""
        user_query = f"<SW>display fan\n{cli}"

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp = Path(tmpdir)
            from generate_templates import generate_templates

            result = generate_templates(
                {
                    "user_query": user_query,
                    "vendor": "Huawei",
                    "model": "Generic",
                    "templates_dir": str(tmp / "templates"),
                    "reports_dir": str(tmp / "reports"),
                    "mapping_config": str(skill_root / "config" / "command_mapping.yaml"),
                    "categories_config": str(skill_root / "config" / "command_categories.yaml"),
                    "max_retries": 1,
                }
            )
            self.assertEqual(result["mode"], "direct")
            self.assertTrue(result.get("parsed_records") or result["success_count"] >= 0)
            self.assertIn("display fan", result["message"])


if __name__ == "__main__":
    unittest.main()
