import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")


class AppsScriptAutomationTests(unittest.TestCase):
    def test_version_is_0_6_0_everywhere(self):
        self.assertIn("VERSION: '0.6.0'", CODE)
        self.assertIn('version = "0.6.0"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn('__version__ = "0.6.0"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8"))

    def test_close_delta_trend_sheet_is_initialized(self):
        self.assertIn("CLOSE_TRENDS: '收盤Delta趨勢'", CODE)
        self.assertIn("CLOSE_TREND_HEADERS:", CODE)
        self.assertIn("function applyCloseTrendFormatting_()", CODE)
        self.assertIn("applyCloseTrendFormatting_();", CODE)

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

    def test_market_event_guard_uses_five_minute_checker(self):
        self.assertIn("function processHourlyGitHubDispatch()", CODE)
        self.assertIn("everyMinutes(5)", CODE)
        self.assertIn("GITHUB_LAST_AUTO_MARKET_EVENT", CODE)
        self.assertRegex(CODE, r"LAST_AUTO_EVENT\).*=== eventKey")
        self.assertIn("hour === 9 && minute >= 30", CODE)
        self.assertIn("hour >= 10 && hour <= 15", CODE)
        self.assertIn("hour === 16 && minute < 30", CODE)
        workflow = (ROOT / ".github" / "workflows" / "option-alerts.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)

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
        self.assertIn("inputs: {force: mode === 'manual' ? 'true' : 'false'}", CODE)
        workflow = (ROOT / ".github" / "workflows" / "option-alerts.yml").read_text(encoding="utf-8")
        self.assertIn("FORCE_REFRESH:", workflow)

    def test_spread_replaces_vega_filter_but_vega_stays_in_chain(self):
        form = (ROOT / "apps-script" / "Index.html").read_text(encoding="utf-8")
        self.assertIn("Bid–Ask Spread條件", form)
        self.assertIn("Delta條件", form)
        self.assertNotIn("|Delta| 絕對值條件", form)
        self.assertNotIn('name="vegaOperator"', form)
        self.assertIn("'Vega估算(每1%)'", CODE)
        self.assertIn("'Gamma估算'", CODE)

    def test_upgrade_clears_old_vega_filter_without_deleting_sheets(self):
        self.assertIn("function migrateScanSchema050_", CODE)
        self.assertIn("headers.indexOf('Vega條件')", CODE)
        self.assertIn("row[vegaOperatorIndex] = ''", CODE)
        self.assertIn("row[baselineIndex] = false", CODE)
        self.assertNotIn("deleteSheet(", CODE)

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
