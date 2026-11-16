import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")


class AppsScriptAutomationTests(unittest.TestCase):
    def test_version_is_0_9_1_everywhere(self):
        self.assertIn("VERSION: '0.9.1'", CODE)
        self.assertIn('version = "0.9.1"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn('__version__ = "0.9.1"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8"))
        self.assertIn('["系統版本", "0.9.1", "目前規格版本"]',
                      (ROOT / "scripts" / "build_workbook.mjs").read_text(encoding="utf-8"))
        self.assertIn('目前版本：`0.9.1`', (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_setup_enforces_display_timezone_and_migrates_visible_times(self):
        self.assertIn("spreadsheet.setSpreadsheetTimeZone(displayTimezone);", CODE)
        self.assertIn("normalizeUserFacingTimestamps_();", CODE)
        self.assertIn("function parseIsoTimestamp_(value)", CODE)
        self.assertIn("normalizeTimestampColumns_(alerts, ['紀錄時間'])", CODE)

    def test_continuing_matches_stay_green(self):
        formatter = re.search(
            r"function applyChainConditionalFormatting_\(sheet\) \{(.*?)\n\}",
            CODE,
            re.S,
        )
        self.assertIsNotNone(formatter)
        self.assertIn('REGEXMATCH($A2,"第二")', formatter.group(1))
        self.assertIn("function applyAllChainFormatting_()", CODE)
        setup = re.search(r"function setupSystem\(\) \{(.*?)\n\}", CODE, re.S)
        self.assertIsNotNone(setup)
        self.assertIn("applyAllChainFormatting_();", setup.group(1))

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
        self.assertIn("operation,", CODE)
        self.assertIn("request_id: job.requestId || ''", CODE)
        workflow = (ROOT / ".github" / "workflows" / "option-alerts.yml").read_text(encoding="utf-8")
        self.assertIn("FORCE_REFRESH:", workflow)

    def test_expiration_lookup_and_batch_scan_ui_are_wired(self):
        form = (ROOT / "apps-script" / "Index.html").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "option-alerts.yml").read_text(encoding="utf-8")
        self.assertIn("function requestExpirationDates(tickerValue)", CODE)
        self.assertIn("function getExpirationQueryStatus(tickerValue, requestIdValue)", CODE)
        self.assertIn("function submitScans(payload)", CODE)
        self.assertIn("MAX_DTE: 365", CODE)
        self.assertIn("到期日查詢等待超過 10 分鐘", CODE)
        self.assertIn("已存在的掃描（預設略過）", form)
        self.assertIn("DTE：${item.dte}", form)
        self.assertIn(".submitScans(data)", form)
        self.assertIn("expiration_lookup", workflow)
        self.assertIn("python -m app.lookup_expirations", workflow)

    def test_close_email_sorts_groups_and_omits_zero_match_sections(self):
        builder = re.search(r"function buildQueueEmail_\(.*?\n\}", CODE, re.S)
        self.assertIsNotNone(builder)
        block = builder.group(0)
        self.assertIn("sourceGroups.filter(group => (group.items || []).length > 0)", block)
        self.assertIn("left.ticker", block)
        self.assertIn("left.expiry", block)
        self.assertIn("本日收盤無符合第一門檻的合約", block)

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

    def test_queue_email_omits_secondary_greeks_and_includes_underlying(self):
        builder = re.search(r"function buildQueueEmail_\(.*?\n\}", CODE, re.S)
        self.assertIsNotNone(builder)
        block = builder.group(0)
        self.assertIn("標的股價", block)
        self.assertNotIn("Gamma", block)
        self.assertNotIn("Theta", block)
        self.assertNotIn("Vega", block)

    def test_notification_queue_has_retry_states(self):
        self.assertIn("QUEUE: '通知佇列'", CODE)
        self.assertIn("'PENDING', 'FAILED'", CODE)
        self.assertIn("setValue('SENDING')", CODE)
        self.assertIn("setValue('SENT')", CODE)
        self.assertIn("重試次數", CODE)

    def test_sent_queue_events_reconcile_every_alert_log_row(self):
        self.assertIn("function reconcileSentAlertLogs_()", CODE)
        self.assertIn("buildAlertLogRowsForEvent_", CODE)
        self.assertIn("'已寄送（0筆符合）'", CODE)
        self.assertIn("'第一門檻'", CODE)
        self.assertIn("'第二門檻'", CODE)
        self.assertIn("'今日新增'", CODE)
        self.assertIn("'紀錄ID'", CODE)
        processor = re.search(r"function processPendingEmails\(\) \{(.*?)\n\}", CODE, re.S)
        self.assertIsNotNone(processor)
        self.assertIn("reconcileAlertLogs_();", processor.group(1))

    def test_realtime_alert_log_uses_complete_snapshot_and_self_repairs(self):
        service = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
        self.assertIn('"all_matching_items": all_realtime_matches', service)
        self.assertIn("group.all_matching_items", CODE)
        self.assertIn("'持續符合（未重複寄信）'", CODE)
        self.assertIn("function ensureAlertLogSheet_()", CODE)
        self.assertIn("spreadsheet.insertSheet(APP.SHEETS.ALERTS)", CODE)
        self.assertIn("'歷史事件僅保存已通知項目'", CODE)
        self.assertIn(".addItem('重建警示紀錄', 'rebuildAlertLog')", CODE)
        self.assertIn("function rebuildAlertLog()", CODE)

    def test_current_matches_are_reconciled_independently_from_email_events(self):
        self.assertIn("function reconcileCurrentMatchLogs_(force)", CODE)
        self.assertIn("function replaceCurrentMatchAlertLogRows_(desiredRows)", CODE)
        self.assertIn("'CURRENT_FIRST'", CODE)
        self.assertIn("'CURRENT_SECOND'", CODE)
        self.assertIn("'最新成功快照'", CODE)
        self.assertIn("reconcileAlertLogs_(true)", CODE)
        self.assertIn("CURRENT_MATCH_TOKEN", CODE)
        self.assertIn("CURRENT_MATCH_COUNT", CODE)
        self.assertIn("function countCurrentMatchAlertLogRows_()", CODE)
        self.assertIn("'紀錄時間'", CODE)

    def test_manual_close_recovery_is_identified_in_alert_log(self):
        service = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
        self.assertIn('"capture_mode": "manual_recovery" if manual_close_recovery else "scheduled_close"', service)
        self.assertIn("payload.capture_mode === 'manual_recovery'", CODE)
        self.assertIn("'完整（延後補抓）'", CODE)

    def test_close_history_uses_one_batch_load_and_retries_sheets_429(self):
        service = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
        sheets = (ROOT / "app" / "sheets.py").read_text(encoding="utf-8")
        self.assertIn("close_existing, previous_closes = self._load_close_history", service)
        self.assertNotIn("self._load_previous_close(scan.scan_id", service)
        self.assertIn("def load_close_history(", sheets)
        self.assertIn("status != 429", sheets)

    def test_scan_migration_removes_legacy_validation_before_writing(self):
        migration = re.search(r"function migrateScanSchema070_\(spreadsheet\) \{(.*?)\n\}", CODE, re.S)
        self.assertIsNotNone(migration)
        block = migration.group(1)
        self.assertIn("clearDataValidations();", block)
        self.assertLess(block.index("clearDataValidations();"), block.index("setValues(migrated)"))
        self.assertNotIn("rewriteRange.clearContent();", block)

    def test_dispatch_acceptance_is_separate_from_data_completion(self):
        self.assertIn("等待資料更新完成", CODE)
        service = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
        self.assertIn("工作流程完成：資料更新成功", service)

    def test_runtime_chain_write_occurs_before_stale_tail_clear(self):
        sheets = (ROOT / "app" / "sheets.py").read_text(encoding="utf-8")
        method = re.search(r"def write_chain_sheets\(.*?\n    def ", sheets, re.S)
        self.assertIsNotNone(method)
        self.assertLess(method.group(0).index("values().batchUpdate"), method.group(0).index("values().batchClear"))


if __name__ == "__main__":
    unittest.main()
