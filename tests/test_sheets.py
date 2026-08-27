import unittest

from app.constants import SCAN_HEADERS
from app.sheets import _is_blank_scan_row


class ScanRowTests(unittest.TestCase):
    def test_unchecked_checkbox_placeholders_are_blank(self):
        row = [False] + [""] * 12 + [False]

        self.assertTrue(_is_blank_scan_row(SCAN_HEADERS, row))

    def test_configured_scan_is_not_blank(self):
        row = [False, "MU|2027-01-15", "MU", "2027-01-15", "ALL"]

        self.assertFalse(_is_blank_scan_row(SCAN_HEADERS, row))


if __name__ == "__main__":
    unittest.main()
