import unittest
from datetime import datetime, timezone

from app.close_trends import build_close_trend_rows, select_delta_candidate
from app.constants import CLOSE_TREND_TARGETS, SCAN_HEADERS
from app.models import ScanRecord


def make_scan(display_type="ALL"):
    row = [
        True,
        "",
        "MU",
        "2027-01-15",
        display_type,
        "",
        "",
        "",
        "",
        "",
        "",
        60,
        "",
        True,
        "",
    ]
    return ScanRecord.from_values(2, SCAN_HEADERS, row)


def chain_row(symbol, option_type, absolute_delta, spread, open_interest, bid=1.5):
    signed_delta = absolute_delta if option_type == "CALL" else -absolute_delta
    return {
        "掃描ID": "MU|2027-01-15",
        "類型": option_type,
        "合約代號": symbol,
        "履約價": 55,
        "標的股價": 60,
        "Last": 1.4,
        "Bid": bid,
        "Ask": 1.6,
        "Mid": 1.55,
        "Bid-Ask價差率": spread,
        "賣出試算價": bid,
        "試算價來源": "Bid",
        "IV": 0.35,
        "無風險利率": 0.03678,
        "股息殖利率": 0.01,
        "Greeks模型": "Black-Scholes-Merton (估算)",
        "Delta估算": signed_delta,
        "Gamma估算": 0.01,
        "Theta估算(每日)": -0.02,
        "Vega估算(每1%)": 0.05,
        "|Delta|": absolute_delta,
        "DTE": 100,
        "年化報酬率": bid / 55 / 100 * 365,
        "年化本金": 55,
        "成交量": 20,
        "未平倉": open_interest,
        "最後成交時間": datetime(2026, 8, 27, 19, 59, tzinfo=timezone.utc),
        "資料狀態": "正常",
    }


class CloseTrendTests(unittest.TestCase):
    def test_selects_closest_delta_without_exceeding_target(self):
        rows = [
            chain_row("P009", "PUT", 0.09, 0.08, 100),
            chain_row("P015", "PUT", 0.15, 0.12, 200),
            chain_row("P016", "PUT", 0.16, 0.05, 500),
        ]
        selected = select_delta_candidate(rows, "PUT", 0.15)
        self.assertEqual(selected["合約代號"], "P015")
        self.assertLessEqual(selected["|Delta|"], 0.15)

    def test_tie_breaks_by_spread_then_open_interest(self):
        rows = [
            chain_row("P_WIDE", "PUT", 0.15, 0.20, 500),
            chain_row("P_LOW_OI", "PUT", 0.15, 0.10, 100),
            chain_row("P_HIGH_OI", "PUT", 0.15, 0.10, 300),
        ]
        selected = select_delta_candidate(rows, "PUT", 0.15)
        self.assertEqual(selected["合約代號"], "P_HIGH_OI")

    def test_builds_six_rows_for_all_types_and_three_targets(self):
        scan = make_scan("ALL")
        rows = []
        for option_type, prefix in (("CALL", "C"), ("PUT", "P")):
            rows.extend(
                [
                    chain_row(f"{prefix}010", option_type, 0.10, 0.10, 100),
                    chain_row(f"{prefix}015", option_type, 0.15, 0.10, 200),
                    chain_row(f"{prefix}020", option_type, 0.20, 0.10, 300),
                ]
            )
        market_close = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)
        captured_at = datetime(2026, 8, 27, 20, 5, tzinfo=timezone.utc)

        result = build_close_trend_rows(
            scans=[scan],
            chain_rows={scan.scan_id: rows},
            scan_updates={},
            market_close=market_close,
            captured_at=captured_at,
            market_timezone="America/New_York",
            risk_free_rate_source="^IRX fast_info.lastPrice",
        )

        self.assertEqual(len(result), 6)
        self.assertEqual({row["目標|Delta|"] for row in result}, set(CLOSE_TREND_TARGETS))
        self.assertTrue(all(row["選取狀態"] == "已選取" for row in result))
        target_put = next(
            row for row in result if row["類型"] == "PUT" and row["目標|Delta|"] == 0.15
        )
        self.assertEqual(target_put["合約代號"], "P015")
        self.assertAlmostEqual(target_put["Delta差距"], 0)
        self.assertAlmostEqual(target_put["到期權利金報酬率"], 1.5 / 55)
        self.assertEqual(target_put["無風險利率來源"], "^IRX fast_info.lastPrice")
        self.assertTrue(target_put["快照ID"].startswith("2026-08-27|"))

    def test_missing_delta_keeps_placeholder_instead_of_skipping_date(self):
        scan = make_scan("PUT")
        row = chain_row("P_MISSING", "PUT", 0.10, 0.10, 100)
        row["Delta估算"] = None
        row["|Delta|"] = None
        result = build_close_trend_rows(
            scans=[scan],
            chain_rows={scan.scan_id: [row]},
            scan_updates={},
            market_close=datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc),
            captured_at=datetime(2026, 8, 27, 20, 5, tzinfo=timezone.utc),
            market_timezone="America/New_York",
            risk_free_rate_source="^IRX history Close",
        )
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item["選取狀態"] == "Greeks不足" for item in result))
        self.assertTrue(all(item.get("年化報酬率") is None for item in result))

    def test_failed_scan_creates_daily_status_rows(self):
        scan = make_scan("PUT")
        result = build_close_trend_rows(
            scans=[scan],
            chain_rows={},
            scan_updates={
                scan.scan_id: {"資料狀態": "抓取失敗", "錯誤訊息": "Yahoo unavailable"}
            },
            market_close=datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc),
            captured_at=datetime(2026, 8, 27, 20, 5, tzinfo=timezone.utc),
            market_timezone="America/New_York",
            risk_free_rate_source="無法取得",
        )
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item["選取狀態"] == "抓取失敗" for item in result))
        self.assertTrue(all(item["備註／未選取原因"] == "Yahoo unavailable" for item in result))


if __name__ == "__main__":
    unittest.main()
