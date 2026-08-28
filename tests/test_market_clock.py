import unittest
from datetime import datetime, timezone

from app.market_clock import get_us_option_session_state


class MarketClockTests(unittest.TestCase):
    def test_regular_equity_option_session(self):
        open_state = get_us_option_session_state(
            datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc)
        )
        closed_state = get_us_option_session_state(
            datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)
        )
        self.assertTrue(open_state.is_open)
        self.assertFalse(closed_state.is_open)
        self.assertFalse(closed_state.just_closed)

    def test_early_close_uses_cboe_equity_option_calendar(self):
        before_close = get_us_option_session_state(
            datetime(2026, 11, 27, 17, 59, tzinfo=timezone.utc)
        )
        after_close = get_us_option_session_state(
            datetime(2026, 11, 27, 18, 10, tzinfo=timezone.utc)
        )
        self.assertTrue(before_close.is_open)
        self.assertTrue(after_close.just_closed)
        self.assertEqual(after_close.market_close.hour, 18)

    def test_exchange_holiday_has_no_session(self):
        state = get_us_option_session_state(
            datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
        )
        self.assertFalse(state.is_open)
        self.assertFalse(state.just_closed)
        self.assertIsNone(state.market_open)


if __name__ == "__main__":
    unittest.main()
