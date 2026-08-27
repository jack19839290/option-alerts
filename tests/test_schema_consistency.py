import re
import unittest
from pathlib import Path

from app.constants import CHAIN_HEADERS, SCAN_HEADERS


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
        apps_block = re.search(r"CHAIN_HEADERS:\s*\[(.*?)\]\s*,", code, re.S)
        self.assertIsNotNone(apps_block)
        self.assertEqual(quoted_values(apps_block.group(1)), CHAIN_HEADERS)

    def test_apps_script_does_not_fill_empty_scan_rows_with_false(self):
        code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")

        self.assertNotIn(".insertCheckboxes()", code)
        self.assertIn("firstAvailableRow", code)
        self.assertIn("clearPlaceholderCheckboxValues_", code)


if __name__ == "__main__":
    unittest.main()
