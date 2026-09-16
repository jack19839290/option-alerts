import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.close_trends import volatility_summary, build_volatility_trend_rows
from app.constants import VOLATILITY_TREND_HEADERS
from app.sheets import SheetsRepository
from test_close_trends import chain_row, make_scan


def quote(symbol, delta, strike, iv, side="PUT"):
    row = chain_row(symbol, side, delta, 0.1, 100)
    row.update({"履約價": strike, "IV": iv, "標的股價": 100})
    return row


class VolatilityTests(unittest.TestCase):
    def test_interpolation_and_percentage_points(self):
        rows = [quote("P1", .05, 75, .6), quote("P2", .15, 85, .5),
                quote("P3", .35, 95, .4), quote("P4", .60, 105, .3),
                quote("C1", .1, 110, .9, "CALL")]
        value = volatility_summary(rows, "PUT")
        self.assertAlmostEqual(value["10Δ IV"], .55)
        self.assertAlmostEqual(value["25Δ IV"], .45)
        self.assertAlmostEqual(value["ATM IV"], .35)
        self.assertAlmostEqual(value["10Δ − 25Δ"], 10)
        self.assertAlmostEqual(value["10Δ − ATM"], 20)
        self.assertIn("P1/P2", value["IV取樣說明"])

    def test_no_extrapolation_or_invalid_quote_fallback(self):
        rows = [quote("P1", .1, 80, .6), quote("P2", .25, 90, .5)]
        rows[1]["Bid"] = 0
        value = volatility_summary(rows, "PUT")
        self.assertEqual(value["10Δ IV"], .6)
        self.assertIsNone(value["25Δ IV"])
        self.assertIsNone(value["ATM IV"])
        self.assertIsNone(value["10Δ − 25Δ"])

    def test_signed_skew_and_exact_atm(self):
        rows = [quote("P1", .1, 80, .3), quote("P2", .25, 90, .4), quote("P3", .5, 100, .5)]
        value = volatility_summary(rows, "PUT")
        self.assertAlmostEqual(value["10Δ − ATM"], -20)
        self.assertEqual(value["ATM IV"], .5)

    def test_one_row_per_type_not_per_delta_and_failed_rows_retained(self):
        scan = make_scan("ALL")
        now = datetime(2026, 9, 17, 20, tzinfo=timezone.utc)
        rows = build_volatility_trend_rows(scans=[scan], chain_rows={}, scan_updates={},
            market_close=now, captured_at=now, market_timezone="America/New_York")
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["類型"] for r in rows}, {"PUT", "CALL"})
        self.assertTrue(all(r["資料狀態"] == "IV資料不足" for r in rows))
        self.assertTrue(all(r["10Δ IV"] is None for r in rows))

    def test_write_is_idempotent_and_recovers_incomplete_rows(self):
        repository = object.__new__(SheetsRepository)
        repository.spreadsheet_id = "test"
        repository.service = MagicMock()
        repository._ensure_sheets = MagicMock()
        repository._ensure_header = MagicMock()
        old = []
        for key, status in (("complete", "正常"), ("failed", "IV資料不足")):
            row = [""] * len(VOLATILITY_TREND_HEADERS)
            row[11], row[15] = status, key
            old.append(row)
        api = repository.service.spreadsheets.return_value.values.return_value
        api.get.return_value.execute.return_value = {"values": old}
        repository.upsert_volatility_trend_rows([
            {"快照ID": key, "資料狀態": "正常", "10Δ IV": .5}
            for key in ("complete", "failed", "new", "new")])
        changes = api.batchUpdate.call_args.kwargs["body"]["data"]
        self.assertEqual(len(changes), 1)
        self.assertIn("A3:P3", changes[0]["range"])
        self.assertEqual(len(api.append.call_args.kwargs["body"]["values"]), 1)


if __name__ == "__main__":
    unittest.main()
