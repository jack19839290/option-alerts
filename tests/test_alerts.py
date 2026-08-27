import unittest

from app.alerts import HIGH, LOW, NORMAL, evaluate_alert


class AlertTests(unittest.TestCase):
    def test_high_crossing_sends_once(self):
        first = evaluate_alert(
            price=4.1,
            low_threshold=2.5,
            high_threshold=4.0,
            previous_state=NORMAL,
            email_enabled=True,
        )
        repeated = evaluate_alert(
            price=4.2,
            low_threshold=2.5,
            high_threshold=4.0,
            previous_state=HIGH,
            email_enabled=True,
        )
        self.assertEqual(first.state, HIGH)
        self.assertEqual(first.pending_email, HIGH)
        self.assertEqual(repeated.pending_email, "")

    def test_high_hysteresis_rearms_only_below_buffer(self):
        still_high = evaluate_alert(
            price=3.95,
            low_threshold=None,
            high_threshold=4.0,
            previous_state=HIGH,
            email_enabled=True,
            hysteresis=0.02,
        )
        rearmed = evaluate_alert(
            price=3.90,
            low_threshold=None,
            high_threshold=4.0,
            previous_state=HIGH,
            email_enabled=True,
            hysteresis=0.02,
        )
        self.assertEqual(still_high.state, HIGH)
        self.assertEqual(rearmed.state, NORMAL)

    def test_low_crossing(self):
        decision = evaluate_alert(
            price=2.4,
            low_threshold=2.5,
            high_threshold=4.0,
            previous_state=NORMAL,
            email_enabled=True,
        )
        self.assertEqual(decision.state, LOW)
        self.assertEqual(decision.pending_email, LOW)


if __name__ == "__main__":
    unittest.main()

