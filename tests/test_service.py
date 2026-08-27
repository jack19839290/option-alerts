import json
import unittest
from datetime import datetime, timezone

from app.constants import SCAN_HEADERS, SETTINGS_DEFAULTS
from app.models import ChainSnapshot, OptionQuote, ScanRecord
from app.provider import RateLimitError
from app.service import RefreshService


class FakeRepository:
    def __init__(self, scans, settings=None, chain_states=None):
        self.scans = scans
        self.settings = dict(SETTINGS_DEFAULTS)
        if settings:
            self.settings.update(settings)
        self.chain_states = chain_states or {}
        self.scan_updates = None
        self.chain_updates = None
        self.logs = []

    def load_settings(self):
        return dict(self.settings)

    def load_scans(self):
        return SCAN_HEADERS, self.scans, []

    def load_chain_states(self, scans):
        return self.chain_states

    def update_scan_outputs(self, headers, scans, updates):
        self.scan_updates = updates

    def write_chain_sheets(self, scans, rows):
        self.chain_updates = rows

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
            underlying_price=60,
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
                    open_interest=101,
                    last_trade_time=datetime(2026, 8, 27, 15, tzinfo=timezone.utc),
                ),
                OptionQuote(
                    contract_symbol="MU270115C00055000",
                    option_type="CALL",
                    strike=55,
                    last_price=7.0,
                    bid=6.8,
                    ask=7.2,
                    implied_volatility=0.35,
                    volume=10,
                    open_interest=200,
                    last_trade_time=datetime(2026, 8, 27, 15, tzinfo=timezone.utc),
                ),
            ],
        )


class RateLimitedProvider(FakeProvider):
    def fetch_chain(self, ticker, expiry):
        raise RateLimitError("429 Too Many Requests")


class DividendWarningProvider(FakeProvider):
    def fetch_chain(self, ticker, expiry):
        snapshot = super().fetch_chain(ticker, expiry)
        snapshot.dividend_yield_note = "股息率資料異常，採用預設值"
        return snapshot


def make_scan(*, baseline=False, fingerprint=""):
    row = [
        True,
        "",
        "MU",
        "2027-01-15",
        "ALL",
        "",
        "",
        "",
        "",
        "≥",
        0.15,
        60,
        100,
        True,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        baseline,
        fingerprint,
    ]
    scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
    if baseline and not fingerprint:
        scan.values["條件指紋"] = scan.condition_fingerprint
    return scan


class ServiceTests(unittest.TestCase):
    def test_github_schedule_uses_five_minute_market_interval(self):
        scan = make_scan()
        repository = FakeRepository(
            [scan],
            {"最後成功抓取(UTC)": "2026-08-27T15:00:00+00:00"},
        )
        now = datetime(2026, 8, 27, 15, 4, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "尚未到更新時間")

    def test_first_scan_writes_full_chain_but_does_not_email(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        rows = repository.chain_updates[scan.scan_id]
        update = repository.scan_updates[scan.scan_id]
        self.assertEqual(result["status"], "成功")
        self.assertEqual(len(rows), 2)
        self.assertEqual(update["合約數"], 2)
        self.assertEqual(update["符合數"], 2)
        self.assertEqual(update["待寄信"], "")
        put = next(row for row in rows if row["類型"] == "PUT")
        call = next(row for row in rows if row["類型"] == "CALL")
        self.assertAlmostEqual(put["年化報酬率"], 3.8 / 55 / put["DTE"] * 365)
        self.assertAlmostEqual(call["年化報酬率"], 6.8 / 60 / call["DTE"] * 365)
        self.assertEqual(put["通知狀態"], "初次基準")

    def test_dividend_yield_warning_is_written_to_data_status(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)

        RefreshService(repository, DividendWarningProvider()).refresh(
            force=True, now=now
        )

        rows = repository.chain_updates[scan.scan_id]
        self.assertTrue(rows)
        self.assertIn("股息率資料異常", rows[0]["資料狀態"])

    def test_later_new_match_creates_aggregated_pending_payload(self):
        scan = make_scan(baseline=True)
        states = {
            scan.scan_id: {
                "MU270115P00055000": {
                    "可再次通知": True,
                    "連續有效不符合": 2,
                },
                "MU270115C00055000": {
                    "可再次通知": False,
                    "連續有效不符合": 0,
                },
            }
        }
        repository = FakeRepository([scan], chain_states=states)
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        payload = json.loads(repository.scan_updates[scan.scan_id]["待寄信"])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["contract_symbol"], "MU270115P00055000")

    def test_condition_change_resets_baseline(self):
        scan = make_scan(baseline=True, fingerprint="old-conditions")
        states = {
            scan.scan_id: {
                "MU270115P00055000": {
                    "可再次通知": True,
                    "連續有效不符合": 2,
                }
            }
        }
        repository = FakeRepository([scan], chain_states=states)
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        self.assertEqual(repository.scan_updates[scan.scan_id]["待寄信"], "")

    def test_rate_limit_sets_backoff(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, RateLimitedProvider()).refresh(force=True, now=now)
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(repository.settings["連續失敗次數"], 1)
        self.assertIn("2026-08-27T15:15:00", repository.settings["下次允許抓取(UTC)"])


if __name__ == "__main__":
    unittest.main()
