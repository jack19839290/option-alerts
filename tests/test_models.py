import unittest

from app.constants import MONITOR_HEADERS
from app.models import MonitorRecord, parse_sheet_date


class ModelTests(unittest.TestCase):
    def test_google_sheet_date_formats(self):
        self.assertEqual(parse_sheet_date("2027/1/15").isoformat(), "2027-01-15")
        self.assertEqual(parse_sheet_date(46402.5).isoformat(), "2027-01-15")

    def test_monitor_parsing_and_id(self):
        row = [
            True,
            "",
            "mu",
            "2027-01-15",
            "put",
            55,
            2.5,
            4.0,
            True,
            "測試",
        ]
        monitor = MonitorRecord.from_values(2, MONITOR_HEADERS, row)
        self.assertEqual(monitor.monitor_id, "MU|2027-01-15|PUT|55")
        self.assertEqual(monitor.sheet_name, "MU_2027-01-15")
        self.assertEqual(monitor.low_threshold, 2.5)

    def test_invalid_option_type(self):
        row = [True, "", "MU", "2027-01-15", "X", 55]
        with self.assertRaisesRegex(ValueError, "CALL 或 PUT"):
            MonitorRecord.from_values(2, MONITOR_HEADERS, row)


if __name__ == "__main__":
    unittest.main()
