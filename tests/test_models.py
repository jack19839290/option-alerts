import unittest

from app.constants import SCAN_HEADERS
from app.models import ScanRecord, parse_sheet_date


class ModelTests(unittest.TestCase):
    def test_google_sheet_date_formats(self):
        self.assertEqual(parse_sheet_date("2027/1/15").isoformat(), "2027-01-15")
        self.assertEqual(parse_sheet_date(46402.5).isoformat(), "2027-01-15")

    def test_scan_parsing_and_id(self):
        values = {"啟用": True, "股票代號": "mu", "到期日": "2027-01-15", "顯示類型": "all",
                  "第一門檻啟用": True, "第一Delta條件": "≥", "第一Delta門檻": 0.2,
                  "第一Bid-Ask價差條件": "≤", "第一Bid-Ask價差門檻": 0.5,
                  "第一年化報酬率條件": "≥", "第一年化報酬率門檻": 0.15,
                  "第一未平倉大於(口)": 100, "CALL持股成本": 60, "Email通知": True, "備註": "測試"}
        row = [values.get(header, "") for header in SCAN_HEADERS]
        scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
        self.assertEqual(scan.scan_id, "MU|2027-01-15")
        self.assertEqual(scan.sheet_name, "MU_2027-01-15")
        self.assertEqual(scan.first_threshold.delta_threshold, 0.2)
        self.assertEqual(scan.first_threshold.spread_threshold, 0.5)
        self.assertTrue(scan.first_threshold.has_active_conditions)
        self.assertEqual(len(scan.first_condition_fingerprint), 16)

    def test_condition_operator_and_threshold_must_be_paired(self):
        values = {"啟用": True, "股票代號": "MU", "到期日": "2027-01-15", "顯示類型": "ALL",
                  "第一門檻啟用": True, "第一Delta條件": "≥", "第一Delta門檻": ""}
        row = [values.get(header, "") for header in SCAN_HEADERS]
        with self.assertRaisesRegex(ValueError, "同時填寫"):
            ScanRecord.from_values(2, SCAN_HEADERS, row)

    def test_blank_conditions_are_allowed(self):
        values = {"啟用": True, "股票代號": "MU", "到期日": "2027-01-15", "顯示類型": "ALL"}
        row = [values.get(header, "") for header in SCAN_HEADERS]
        scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
        self.assertFalse(scan.first_threshold.has_active_conditions)


if __name__ == "__main__":
    unittest.main()
