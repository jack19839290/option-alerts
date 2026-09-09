import unittest

from app.alerts import evaluate_conditions, evaluate_contract_alert
from app.constants import SCAN_HEADERS
from app.models import ScanRecord


def make_scan():
    values = {"啟用": True, "股票代號": "MU", "到期日": "2027-01-15", "顯示類型": "ALL",
              "第一門檻啟用": True, "第一Delta條件": "≥", "第一Delta門檻": 0.2,
              "第一Bid-Ask價差條件": "≤", "第一Bid-Ask價差門檻": 0.5,
              "第一年化報酬率條件": "≥", "第一年化報酬率門檻": 0.15,
              "第一未平倉大於(口)": 100, "CALL持股成本": 60, "Email通知": True}
    row = [values.get(header, "") for header in SCAN_HEADERS]
    return ScanRecord.from_values(2, SCAN_HEADERS, row)


class AlertTests(unittest.TestCase):
    def test_all_active_conditions_use_and_logic_and_absolute_delta(self):
        scan = make_scan()
        result = evaluate_conditions(
            conditions=scan.first_threshold,
            delta=-0.30,
            spread_rate=0.20,
            annual_return=0.18,
            open_interest=101,
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.delta_result, "通過")

    def test_missing_active_metric_is_not_a_match(self):
        scan = make_scan()
        result = evaluate_conditions(
            conditions=scan.first_threshold,
            delta=-0.30,
            spread_rate=0.20,
            annual_return=None,
            open_interest=101,
        )
        self.assertIsNone(result.matched)

    def test_open_interest_condition_is_strictly_greater_than(self):
        scan = make_scan()
        result = evaluate_conditions(
            conditions=scan.first_threshold,
            delta=-0.30,
            spread_rate=0.20,
            annual_return=0.18,
            open_interest=100,
        )
        self.assertFalse(result.matched)
        self.assertEqual(result.open_interest_result, "未通過")

    def test_first_scan_is_baseline_and_later_new_match_sends(self):
        evaluation = evaluate_conditions(
            conditions=make_scan().first_threshold,
            delta=-0.30,
            spread_rate=0.20,
            annual_return=0.18,
            open_interest=101,
        )
        first = evaluate_contract_alert(
            evaluation=evaluation,
            previous_armed=None,
            previous_nonmatches=0,
            previous_sequence=1,
            email_enabled=True,
        )
        later = evaluate_contract_alert(
            evaluation=evaluation,
            previous_armed=True,
            previous_nonmatches=2,
            previous_sequence=1,
            email_enabled=True,
        )
        self.assertEqual(first.status, "新符合")
        self.assertTrue(first.pending_email)
        self.assertTrue(later.pending_email)

    def test_two_valid_nonmatches_are_required_to_rearm(self):
        scan = make_scan()
        no_match = evaluate_conditions(
            conditions=scan.first_threshold,
            delta=-0.10,
            spread_rate=0.20,
            annual_return=0.18,
            open_interest=101,
        )
        first = evaluate_contract_alert(
            evaluation=no_match,
            previous_armed=False,
            previous_nonmatches=0,
            previous_sequence=1,
            email_enabled=True,
        )
        second = evaluate_contract_alert(
            evaluation=no_match,
            previous_armed=first.armed,
            previous_nonmatches=first.consecutive_nonmatches,
            previous_sequence=first.sequence,
            email_enabled=True,
        )
        self.assertFalse(first.armed)
        self.assertTrue(second.armed)


if __name__ == "__main__":
    unittest.main()
