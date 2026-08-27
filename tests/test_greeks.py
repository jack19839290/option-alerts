import unittest
from datetime import date, datetime, timezone

from app.greeks import calculate_greeks


class GreeksTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc)
        self.expiry = date(2027, 1, 1)

    def test_call_reference_values(self):
        result = calculate_greeks(
            option_type="CALL",
            spot=100,
            strike=100,
            volatility=0.20,
            risk_free_rate=0.05,
            dividend_yield=0,
            expiry=self.expiry,
            now=self.now,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.delta, 0.63683, places=4)
        self.assertAlmostEqual(result.vega_per_pct, 0.37524, places=4)
        self.assertAlmostEqual(result.theta_per_day, -0.01757, places=4)

    def test_put_delta_is_negative(self):
        result = calculate_greeks(
            option_type="PUT",
            spot=100,
            strike=100,
            volatility=0.20,
            risk_free_rate=0.05,
            dividend_yield=0,
            expiry=self.expiry,
            now=self.now,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.delta, -0.36317, places=4)

    def test_expired_contract_returns_none(self):
        result = calculate_greeks(
            option_type="CALL",
            spot=100,
            strike=100,
            volatility=0.20,
            risk_free_rate=0.05,
            dividend_yield=0,
            expiry=date(2025, 12, 31),
            now=self.now,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

