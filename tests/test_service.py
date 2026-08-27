import unittest
from datetime import date, datetime, timezone

from app.constants import MONITOR_HEADERS, SETTINGS_DEFAULTS
from app.models import ChainSnapshot, MonitorRecord, OptionQuote
from app.provider import RateLimitError
from app.service import RefreshService


class FakeRepository:
    def __init__(self, monitors, settings=None):
        self.monitors = monitors
        self.settings = dict(SETTINGS_DEFAULTS)
        if settings:
            self.settings.update(settings)
        self.monitor_updates = None
        self.contract_updates = None
        self.logs = []

    def load_settings(self):
        return dict(self.settings)

    def load_monitors(self):
        return MONITOR_HEADERS, self.monitors, []

    def update_monitor_outputs(self, headers, monitors, updates):
        self.monitor_updates = updates

    def write_contract_sheets(self, monitors, updates):
        self.contract_updates = updates

    def update_settings(self, updates):
        self.settings.update(updates)

    def append_system_log(self, level, message, details=""):
        self.logs.append((level, message, details))


class FakeProvider:
    def fetch_risk_free_rate(self, symbol, fallback):
        return 0.05

    def fetch_chain(self, ticker, expiry):
        return ChainSnapshot(
            ticker=ticker,
            expiry=expiry,
            underlying_price=100,
            dividend_yield=0,
            quotes=[
                OptionQuote(
                    contract_symbol="MU270115P00055000",
                    option_type="PUT",
                    strike=55,
                    last_price=3.2,
                    bid=3.8,
                    ask=4.2,
                    implied_volatility=0.35,
                    volume=20,
                    open_interest=100,
                    last_trade_time=datetime(2026, 8, 27, 15, tzinfo=timezone.utc),
                )
            ],
        )


class RateLimitedProvider(FakeProvider):
    def fetch_chain(self, ticker, expiry):
        raise RateLimitError("429 Too Many Requests")


def make_monitor():
    row = [True, "", "MU", "2027-01-15", "PUT", 55, 2.5, 4.0, True, ""]
    return MonitorRecord.from_values(2, MONITOR_HEADERS, row)


class ServiceTests(unittest.TestCase):
    def test_github_schedule_uses_five_minute_market_interval(self):
        monitor = make_monitor()
        repository = FakeRepository(
            [monitor],
            {"最後成功抓取(UTC)": "2026-08-27T15:00:00+00:00"},
        )
        now = datetime(2026, 8, 27, 15, 4, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "尚未到更新時間")

    def test_refresh_updates_quote_greeks_and_alert(self):
        monitor = make_monitor()
        repository = FakeRepository([monitor])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        update = repository.monitor_updates[monitor.monitor_id]
        self.assertEqual(result["status"], "成功")
        self.assertEqual(update["警示採用價"], 4.0)
        self.assertEqual(update["價格來源"], "Mid")
        self.assertEqual(update["警示狀態"], "高於上限")
        self.assertEqual(update["待寄信"], "高於上限")
        self.assertLess(update["Delta估算"], 0)
        self.assertEqual(update["無風險利率"], 0.05)
        self.assertEqual(update["股息殖利率"], 0)
        self.assertEqual(update["Greeks模型"], "Black-Scholes-Merton (估算)")

    def test_rate_limit_sets_backoff(self):
        monitor = make_monitor()
        repository = FakeRepository([monitor])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, RateLimitedProvider()).refresh(force=True, now=now)
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(repository.settings["連續失敗次數"], 1)
        self.assertIn("2026-08-27T15:15:00", repository.settings["下次允許抓取(UTC)"])


if __name__ == "__main__":
    unittest.main()
