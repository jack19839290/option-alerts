import unittest

from app.constants import SCAN_HEADERS
from app.models import ScanRecord, parse_sheet_date


class ModelTests(unittest.TestCase):
    def test_google_sheet_date_formats(self):
        self.assertEqual(parse_sheet_date("2027/1/15").isoformat(), "2027-01-15")
        self.assertEqual(parse_sheet_date(46402.5).isoformat(), "2027-01-15")

    def test_scan_parsing_and_id(self):
        row = [
            True,
            "",
            "mu",
            "2027-01-15",
            "all",
            "≥",
            0.2,
            "≤",
            0.5,
            "≥",
            0.15,
            60,
            100,
            True,
            "測試",
        ]
        scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
        self.assertEqual(scan.scan_id, "MU|2027-01-15")
        self.assertEqual(scan.sheet_name, "MU_2027-01-15")
        self.assertEqual(scan.delta_threshold, 0.2)
        self.assertTrue(scan.has_active_conditions)
        self.assertEqual(len(scan.condition_fingerprint), 16)

    def test_condition_operator_and_threshold_must_be_paired(self):
        row = [True, "", "MU", "2027-01-15", "ALL", "≥", ""]
        with self.assertRaisesRegex(ValueError, "同時填寫"):
            ScanRecord.from_values(2, SCAN_HEADERS, row)

    def test_blank_conditions_are_allowed(self):
        row = [True, "", "MU", "2027-01-15", "ALL"]
        scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
        self.assertFalse(scan.has_active_conditions)


if __name__ == "__main__":
    unittest.main()
