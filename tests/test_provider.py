import unittest
from datetime import date, datetime

from app.greeks import calculate_greeks
from app.provider import (
    YahooFinanceProvider,
    _normalize_yahoo_rate,
    _select_dividend_yield,
)


class FakeIloc:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        return self.values[index]


class FakeClose:
    def __init__(self, values):
        self.values = [value for value in values if value is not None]
        self.iloc = FakeIloc(self.values)

    def dropna(self):
        return self

    @property
    def empty(self):
        return not self.values


class FakeTicker:
    def __init__(self, fast_info=None, closes=None):
        self.fast_info = fast_info or {}
        self.closes = closes or []
        self.history_calls = 0

    def history(self, **kwargs):
        self.history_calls += 1
        return {"Close": FakeClose(self.closes)}


class FakeYFinance:
    def __init__(self, ticker):
        self.ticker = ticker

    def Ticker(self, symbol):
        return self.ticker


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


class RiskFreeRateTests(unittest.TestCase):
    def test_irx_uses_current_yfinance_camel_case_field(self):
        ticker = FakeTicker(fast_info={"lastPrice": 3.678})
        provider = YahooFinanceProvider()
        provider._yf = lambda: FakeYFinance(ticker)

        rate = provider.fetch_risk_free_rate("^IRX", 0.05)

        self.assertAlmostEqual(rate, 0.03678)
        self.assertEqual(provider.risk_free_rate_source, "^IRX fast_info.lastPrice")
        self.assertEqual(ticker.history_calls, 0)

    def test_old_snake_case_field_remains_supported(self):
        ticker = FakeTicker(fast_info={"last_price": 3.5})
        provider = YahooFinanceProvider()
        provider._yf = lambda: FakeYFinance(ticker)

        self.assertAlmostEqual(provider.fetch_risk_free_rate("^IRX", 0.05), 0.035)
        self.assertEqual(provider.risk_free_rate_source, "^IRX fast_info.last_price")

    def test_recent_close_is_used_before_configured_fallback(self):
        ticker = FakeTicker(closes=[3.69, 3.678])
        provider = YahooFinanceProvider()
        provider._yf = lambda: FakeYFinance(ticker)

        self.assertAlmostEqual(provider.fetch_risk_free_rate("^IRX", 0.05), 0.03678)
        self.assertEqual(provider.risk_free_rate_source, "^IRX 最近交易日 Close")

    def test_configured_fallback_is_identified(self):
        provider = YahooFinanceProvider()
        provider._yf = lambda: FakeYFinance(FakeTicker())

        self.assertEqual(provider.fetch_risk_free_rate("^IRX", 0.05), 0.05)
        self.assertIn("採用備援利率", provider.risk_free_rate_note)

    def test_irx_is_always_percentage_points_even_below_one(self):
        self.assertAlmostEqual(_normalize_yahoo_rate(0.5, "^IRX"), 0.005)


if __name__ == "__main__":
    unittest.main()
