import unittest
from datetime import date, datetime

from app.greeks import calculate_greeks
from app.provider import _select_dividend_yield


class DividendYieldTests(unittest.TestCase):
    def test_prefers_trailing_decimal_yield(self):
        value, note = _select_dividend_yield(
            {
                "trailingAnnualDividendYield": 0.0047,
                "dividendYield": 0.47,
            },
            0.0,
        )

        self.assertAlmostEqual(value, 0.0047)
        self.assertEqual(note, "")

    def test_percentage_point_yield_is_divided_by_one_hundred(self):
        value, note = _select_dividend_yield({"dividendYield": 0.47}, 0.0)

        self.assertAlmostEqual(value, 0.0047)
        self.assertEqual(note, "")

    def test_implausible_yield_uses_fallback_and_reports_warning(self):
        value, note = _select_dividend_yield({"dividendYield": 47.0}, 0.01)

        self.assertAlmostEqual(value, 0.01)
        self.assertEqual(note, "股息率資料異常，採用預設值")

    def test_nvda_reported_case_uses_fractional_dividend_yield(self):
        dividend_yield, _ = _select_dividend_yield(
            {"dividendYield": 0.47}, 0.0
        )

        greeks = calculate_greeks(
            option_type="PUT",
            spot=227.98,
            strike=200,
            volatility=0.3786,
            risk_free_rate=0.05,
            dividend_yield=dividend_yield,
            expiry=date(2027, 3, 19),
            now=datetime.fromisoformat("2026-08-27T21:20:20.099890+00:00"),
        )

        self.assertIsNotNone(greeks)
        self.assertAlmostEqual(greeks.delta, -0.243319, places=6)
        self.assertAlmostEqual(greeks.gamma, 0.004849, places=6)
        self.assertAlmostEqual(greeks.theta_per_day, -0.041119, places=6)
        self.assertAlmostEqual(greeks.vega_per_pct, 0.533093, places=6)


if __name__ == "__main__":
    unittest.main()
