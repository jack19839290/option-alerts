import re
import unittest
from pathlib import Path

from app.constants import ALERT_LOG_HEADERS, CHAIN_HEADERS, CLOSE_ALERT_STATE_HEADERS, CLOSE_TREND_HEADERS, SCAN_HEADERS


ROOT = Path(__file__).resolve().parents[1]


def quoted_values(block: str) -> list[str]:
    return [single or double for single, double in re.findall(r"'([^']*)'|\"([^\"]*)\"", block)]


class SchemaConsistencyTests(unittest.TestCase):
    def test_python_apps_script_and_template_scan_headers_match(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8")
        apps_block = re.search(r"SCAN_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        builder_block = re.search(r"const scanHeaders = \[(.*?)\];", builder, re.S)
        self.assertIsNotNone(apps_block)
        self.assertIsNotNone(builder_block)
        self.assertEqual(quoted_values(apps_block.group(1)), SCAN_HEADERS)
        self.assertEqual(quoted_values(builder_block.group(1)), SCAN_HEADERS)

    def test_python_and_apps_script_chain_headers_match(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8")
        apps_block = re.search(r"CHAIN_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        builder_block = re.search(r"const chainHeaders = \[(.*?)\];", builder, re.S)
        self.assertIsNotNone(apps_block)
        self.assertIsNotNone(builder_block)
        self.assertEqual(quoted_values(apps_block.group(1)), CHAIN_HEADERS)
        self.assertEqual(quoted_values(builder_block.group(1)), CHAIN_HEADERS)
        self.assertLess(CHAIN_HEADERS.index("Delta估算"), CHAIN_HEADERS.index("Gamma估算"))
        self.assertEqual(CHAIN_HEADERS[:3], ["符合門檻", "第一門檻結果", "第二門檻結果"])

    def test_close_trend_headers_match_python_apps_script_and_template(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8")
        apps_block = re.search(r"CLOSE_TREND_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        builder_block = re.search(r"const closeTrendHeaders = \[(.*?)\];", builder, re.S)
        self.assertIsNotNone(apps_block)
        self.assertIsNotNone(builder_block)
        self.assertEqual(quoted_values(apps_block.group(1)), CLOSE_TREND_HEADERS)
        self.assertEqual(quoted_values(builder_block.group(1)), CLOSE_TREND_HEADERS)

    def test_close_state_headers_match_python_apps_script_and_template(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8")
        apps_block = re.search(r"CLOSE_STATE_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        builder_block = re.search(r'closeState\.getRange\("A1:J1"\)\.values\s*=\s*\[\[(.*?)\]\];', builder, re.S)
        self.assertIsNotNone(apps_block)
        self.assertIsNotNone(builder_block)
        self.assertEqual(quoted_values(apps_block.group(1)), CLOSE_ALERT_STATE_HEADERS)
        self.assertEqual(quoted_values(builder_block.group(1)), CLOSE_ALERT_STATE_HEADERS)

    def test_alert_log_headers_match_python_apps_script_and_template(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8")
        apps_block = re.search(r"ALERT_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        builder_block = re.search(r"const alertHeaders = \[(.*?)\];", builder, re.S)
        self.assertIsNotNone(apps_block)
        self.assertIsNotNone(builder_block)
        self.assertEqual(quoted_values(apps_block.group(1)), ALERT_LOG_HEADERS)
        self.assertEqual(quoted_values(builder_block.group(1)), ALERT_LOG_HEADERS)

    def test_apps_script_does_not_fill_empty_scan_rows_with_false(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")

        self.assertNotIn(".insertCheckboxes()", code)
        self.assertIn("firstAvailableRow", code)
        self.assertIn("clearPlaceholderCheckboxValues_", code)


if __name__ == "__main__":
    unittest.main()
