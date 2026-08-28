import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")


class AppsScriptAutomationTests(unittest.TestCase):
    def test_version_is_0_4_0_everywhere(self):
        self.assertIn("VERSION: '0.4.0'", CODE)
        self.assertIn('version = "0.4.0"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn('__version__ = "0.4.0"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8"))

    def test_legacy_migration_and_compatibility_code_are_removed(self):
        for forbidden in (
            "LEGACY_MONITORS",
            "migrateLegacySheets_",
            "nextAvailableSheetName_",
            "showMonitorDialog",
            "submitMonitor",
            "監控清單_舊版",
            "警示紀錄_舊版",
        ):
            self.assertNotIn(forbidden, CODE)
        constants = (ROOT / "app" / "constants.py").read_text(encoding="utf-8")
        self.assertNotIn("LEGACY_MONITOR_SHEET", constants)

    def test_manifest_allows_github_request(self):
        manifest = json.loads((ROOT / "apps-script" / "appsscript.json").read_text(encoding="utf-8"))
        self.assertIn(
            "https://www.googleapis.com/auth/script.external_request",
            manifest["oauthScopes"],
        )

    def test_hourly_guard_uses_five_minute_checker(self):
        self.assertIn("function processHourlyGitHubDispatch()", CODE)
        self.assertIn("everyMinutes(5)", CODE)
        self.assertIn("GITHUB_LAST_AUTO_ATTEMPT_HOUR", CODE)
        self.assertRegex(CODE, r"LAST_AUTO_HOUR\).*=== hourKey")
        workflow = (ROOT / ".github" / "workflows" / "option-alerts.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '2 * * * *'", workflow)
        self.assertNotIn("2,7,12,17", workflow)

    def test_manual_controls_dispatch_real_workflow(self):
        self.assertIn(".addItem('立即手動更新', 'runManualRefresh')", CODE)
        self.assertIn("function handleDashboardAction(event)", CODE)
        self.assertIn("range.getA1Notation() !== 'H7'", CODE)
        self.assertIsNotNone(
            re.search(
                r"function runManualRefresh_\(showToast\).*?dispatchGitHubWorkflow_\('manual'\)",
                CODE,
                re.S,
            )
        )

    def test_dispatch_accepts_github_success_codes(self):
        self.assertIn("code !== 200 && code !== 204", CODE)
        self.assertIn("/dispatches", CODE)
        self.assertIn("JSON.stringify({ref: APP.GITHUB.REF})", CODE)

    def test_token_is_kept_in_user_properties(self):
        self.assertIn("PropertiesService.getUserProperties()", CODE)
        self.assertNotIn("getScriptProperties().setProperty(APP.PROPERTIES.TOKEN", CODE)
        self.assertNotIn("setValue(token)", CODE)
        self.assertNotIn("'GitHub 金鑰': token", CODE)

    def test_failure_notification_and_expiry_thresholds_exist(self):
        self.assertIn("24 * 60 * 60 * 1000", CODE)
        self.assertIn("daysLeft > 7", CODE)
        self.assertIn("LAST_EXPIRY_NOTICE_DATE, expiresOn", CODE)
        self.assertIn("91 * 24 * 60 * 60 * 1000", CODE)
        self.assertIn("自動更新已恢復", CODE)


if __name__ == "__main__":
    unittest.main()
