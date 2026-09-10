import unittest
from datetime import datetime, timezone

from app.constants import SCAN_HEADERS, SETTINGS_DEFAULTS
from app.models import ChainSnapshot, OptionQuote, ScanRecord
from app.provider import MarketDataError, RateLimitError
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
        self.close_trend_updates = []
        self.notification_events = []
        self.close_records = {}
        self.previous_close = {}
        self.close_history_loads = 0
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

    def upsert_close_trend_rows(self, rows):
        self.close_trend_updates.extend(rows)

    def append_notification_events(self, events):
        self.notification_events.extend(events)

    def load_close_records(self, market_date):
        return dict(self.close_records.get(market_date, {}))

    def load_close_history(self, market_date):
        self.close_history_loads += 1
        return dict(self.close_records.get(market_date, {})), dict(self.previous_close)

    def load_previous_close_record(self, scan_id, market_date):
        return self.previous_close.get(scan_id)

    def upsert_close_records(self, records):
        for record in records:
            self.close_records.setdefault(record["market_date"], {})[record["scan_id"]] = {
                "狀態": record["status"], "第一條件指紋": record["fingerprint"]
            }

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


class FallbackRateProvider(FakeProvider):
    def fetch_risk_free_rate(self, symbol, fallback):
        self.risk_free_rate_source = "設定備援值"
        self.risk_free_rate_note = f"{symbol} 即時值與最近收盤均無法取得，採用備援利率"
        return fallback


def make_scan(*, second=False, second_fingerprint="", ticker="MU"):
    values = {"啟用": True, "股票代號": ticker, "到期日": "2027-01-15", "顯示類型": "ALL",
              "第一門檻啟用": True, "第一年化報酬率條件": "≥", "第一年化報酬率門檻": 0.15,
              "第一未平倉大於(口)": 100, "CALL持股成本": 60, "Email通知": True,
              "第二門檻啟用": second, "第二年化報酬率條件": "≥" if second else "",
              "第二年化報酬率門檻": 0.15 if second else "", "第二未平倉大於(口)": 100 if second else "",
              "第二條件指紋": second_fingerprint}
    row = [values.get(header, "") for header in SCAN_HEADERS]
    scan = ScanRecord.from_values(2, SCAN_HEADERS, row)
    if second and not second_fingerprint:
        scan.values["第二條件指紋"] = scan.second_condition_fingerprint
    return scan


class PartialProvider(FakeProvider):
    def fetch_chain(self, ticker, expiry):
        if ticker == "BAD":
            raise MarketDataError("Yahoo unavailable")
        return super().fetch_chain(ticker, expiry)


class NoMatchProvider(FakeProvider):
    def fetch_chain(self, ticker, expiry):
        snapshot = super().fetch_chain(ticker, expiry)
        for quote in snapshot.quotes:
            quote.open_interest = 0
        return snapshot


class ServiceTests(unittest.TestCase):
    def test_automatic_refresh_skips_outside_option_session(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "非期權開盤或收盤更新時點")

    def test_manual_refresh_is_allowed_outside_option_session(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        self.assertEqual(result["status"], "成功")
        self.assertEqual(result["market_open"], False)

    def test_automatic_refresh_runs_during_option_session(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "成功")
        self.assertEqual(result["market_open"], True)

    def test_close_dispatch_has_grace_window(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 20, 45, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "成功")
        self.assertEqual(result["close_update"], True)
        self.assertEqual(result["close_trend_rows"], 6)
        self.assertEqual(len(repository.close_trend_updates), 6)

    def test_manual_refresh_after_failed_close_recovers_close_snapshot(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 28, 3, 45, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        self.assertEqual(result["status"], "成功")
        self.assertTrue(result["close_update"])
        self.assertTrue(result["close_recovery"])
        self.assertEqual(result["close_trend_rows"], 6)
        self.assertEqual(repository.notification_events[0]["事件類型"], "FIRST_CLOSE")
        self.assertEqual(repository.notification_events[0]["內容JSON"]["capture_mode"], "manual_recovery")

    def test_manual_refresh_after_completed_close_does_not_duplicate_close_event(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        repository.close_records["2026-08-27"] = {scan.scan_id: {"狀態": "SUCCESS"}}
        now = datetime(2026, 8, 28, 3, 45, tzinfo=timezone.utc)

        result = RefreshService(repository, FakeProvider()).refresh(force=True, now=now)

        self.assertEqual(result["status"], "成功")
        self.assertFalse(result["close_update"])
        self.assertFalse(result["close_recovery"])
        self.assertEqual(result["close_trend_rows"], 0)
        self.assertEqual(repository.notification_events, [])

    def test_close_dispatch_is_written_only_once(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        repository.close_records["2026-08-27"] = {scan.scan_id: {"狀態": "SUCCESS"}}
        now = datetime(2026, 8, 27, 20, 20, tzinfo=timezone.utc)
        result = RefreshService(repository, FakeProvider()).refresh(now=now)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "本交易日收盤更新已完整完成")

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
        self.assertEqual(update["第一符合數"], 2)
        self.assertEqual(update["第二符合數"], 0)
        put = next(row for row in rows if row["類型"] == "PUT")
        call = next(row for row in rows if row["類型"] == "CALL")
        self.assertAlmostEqual(put["年化報酬率"], 3.8 / 55 / put["DTE"] * 365)
        self.assertAlmostEqual(call["年化報酬率"], 6.8 / 60 / call["DTE"] * 365)
        self.assertAlmostEqual(put["Bid-Ask價差率"], 0.10)
        self.assertIsNotNone(put["Gamma估算"])
        self.assertEqual(put["第二通知狀態"], "停用")

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

    def test_risk_free_fallback_is_visible_in_data_status(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)

        result = RefreshService(repository, FallbackRateProvider()).refresh(
            force=True, now=now
        )

        rows = repository.chain_updates[scan.scan_id]
        self.assertIn("採用備援利率", rows[0]["資料狀態"])
        self.assertEqual(result["risk_free_rate_source"], "設定備援值")

    def test_second_threshold_new_match_creates_queue_event(self):
        scan = make_scan(second=True)
        states = {
            scan.scan_id: {
                "MU270115P00055000": {
                    "第二可再次通知": True,
                    "第二連續有效不符合": 2,
                    "第二通知序號": 1,
                },
                "MU270115C00055000": {
                    "第二可再次通知": False,
                    "第二連續有效不符合": 0,
                    "第二通知序號": 1,
                },
            }
        }
        repository = FakeRepository([scan], chain_states=states)
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        self.assertEqual(len(repository.notification_events), 1)
        payload = repository.notification_events[0]["內容JSON"]
        self.assertEqual(payload["groups"][0]["items"][0]["contract_symbol"], "MU270115P00055000")
        snapshot = payload["groups"][0]["all_matching_items"]
        self.assertEqual({item["contract_symbol"] for item in snapshot}, {
            "MU270115P00055000", "MU270115C00055000"
        })
        triggered = {item["contract_symbol"]: item["triggered_now"] for item in snapshot}
        self.assertTrue(triggered["MU270115P00055000"])
        self.assertFalse(triggered["MU270115C00055000"])

    def test_second_condition_change_notifies_current_matches(self):
        scan = make_scan(second=True, second_fingerprint="old-conditions")
        states = {
            scan.scan_id: {
                "MU270115P00055000": {
                    "第二可再次通知": False,
                    "第二連續有效不符合": 0,
                }
            }
        }
        repository = FakeRepository([scan], chain_states=states)
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        RefreshService(repository, FakeProvider()).refresh(force=True, now=now)
        self.assertEqual(len(repository.notification_events), 1)

    def test_rate_limit_sets_backoff(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
        result = RefreshService(repository, RateLimitedProvider()).refresh(force=True, now=now)
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(repository.settings["連續失敗次數"], 1)
        self.assertIn("2026-08-27T15:15:00", repository.settings["下次允許抓取(UTC)"])

    def test_close_zero_matches_still_queues_daily_email(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        now = datetime(2026, 8, 27, 20, 45, tzinfo=timezone.utc)
        RefreshService(repository, NoMatchProvider()).refresh(now=now)
        event = repository.notification_events[0]
        self.assertEqual(event["事件類型"], "FIRST_CLOSE")
        self.assertEqual(event["內容JSON"]["groups"][0]["items"], [])
        self.assertEqual(event["內容JSON"]["capture_mode"], "scheduled_close")

    def test_close_marks_new_contract_against_previous_valid_close(self):
        scan = make_scan()
        repository = FakeRepository([scan])
        repository.previous_close[scan.scan_id] = {
            "fingerprint": scan.first_condition_fingerprint,
            "symbols": ["MU270115C00055000"],
        }
        now = datetime(2026, 8, 27, 20, 45, tzinfo=timezone.utc)
        RefreshService(repository, FakeProvider()).refresh(now=now)
        items = repository.notification_events[0]["內容JSON"]["groups"][0]["items"]
        flags = {item["contract_symbol"]: item["is_new"] for item in items}
        self.assertTrue(flags["MU270115P00055000"])
        self.assertFalse(flags["MU270115C00055000"])
        self.assertEqual(repository.close_history_loads, 1)

    def test_many_close_scans_load_close_history_only_once(self):
        scans = [make_scan(ticker=f"T{i}") for i in range(25)]
        repository = FakeRepository(scans)
        now = datetime(2026, 8, 27, 20, 45, tzinfo=timezone.utc)

        RefreshService(repository, FakeProvider()).refresh(now=now)

        self.assertEqual(repository.close_history_loads, 1)

    def test_partial_success_does_not_advance_last_complete_success(self):
        good, bad = make_scan(), make_scan(ticker="BAD")
        previous = "2026-08-26T20:10:00+00:00"
        repository = FakeRepository([good, bad], {"最後成功抓取(UTC)": previous})
        now = datetime(2026, 8, 27, 20, 45, tzinfo=timezone.utc)
        result = RefreshService(repository, PartialProvider()).refresh(now=now)
        self.assertEqual(result["status"], "部分成功")
        self.assertEqual(repository.settings["最後成功抓取(UTC)"], previous)
        self.assertEqual(repository.close_records["2026-08-27"][bad.scan_id]["狀態"], "FAILED")
        self.assertFalse(repository.notification_events[0]["是否完整"])


if __name__ == "__main__":
    unittest.main()
