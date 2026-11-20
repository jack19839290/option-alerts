import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import ChainSnapshot, OptionQuote
from long_call.put import DEFAULTS, FAILED, HEADERS, PENDING, evaluate, thresholds


class ProtectivePutTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 2, 18, tzinfo=timezone.utc)
        expiry = (self.now + timedelta(days=90)).date()
        self.chain = ChainSnapshot("NVDA", expiry, 100, 0)
        self.quote = OptionQuote(f"NVDA{expiry:%y%m%d}P00090000", "PUT", 90, None,
                                 1.90, 2.00, 0.5, 100, 500, self.now, "REGULAR")
        self.limits = thresholds(DEFAULTS)

    def evaluate(self, quote=None):
        row = evaluate(self.chain, quote or self.quote, self.limits, self.now, self.now, 0.04)
        return dict(zip(HEADERS, row, strict=True))

    def test_hedge_formulas_and_unverified_quote_time(self):
        row = self.evaluate()
        self.assertEqual(row["每口保費"], 200)
        self.assertEqual(row["每口 Bid 估值"], 190)
        self.assertEqual(row["保費率"], 0.02)
        self.assertAlmostEqual(row["年化成本"], 0.081111111)
        self.assertEqual(row["最大到期跌幅"], 0.12)
        self.assertLess(row["Delta"], 0)
        self.assertEqual(row["狀態"], PENDING)
        self.assertEqual(row["篩選原因"], "")
        self.assertIsNone(row["Put 報價時間"])
        self.assertIsNotNone(row["最後成交 UTC"])
        for drop, efficiency in [(10, -0.2), (20, 0.4), (30, 0.6), (40, 0.7)]:
            self.assertEqual(row[f"跌 {drop}% 組合損益"], -1200)
            self.assertEqual(row[f"跌 {drop}% 避險效率"], efficiency)

    def test_each_violation_reported_and_boundaries_inclusive(self):
        self.limits.update({"最大跌幅": (Decimal(".12"),), "保費率": (Decimal(".02"),)})
        self.assertEqual(self.evaluate()["篩選原因"], "")
        row = self.evaluate(replace(self.quote, ask=4, open_interest=100))
        self.assertEqual(row["狀態"], FAILED)
        for reason in ["OI 不足", "Spread 超標", "保費率 超標", "年化成本 超標", "最大跌幅 超標"]:
            self.assertIn(reason, row["篩選原因"])

    def test_missing_oi_can_be_ignored_without_fabricating_value(self):
        quote = replace(self.quote, open_interest=None)
        self.assertIn("OI 無法判定", self.evaluate(quote)["篩選原因"])
        self.limits["OI"] = None
        row = self.evaluate(quote)
        self.assertEqual(row["篩選原因"], "")
        self.assertIsNone(row["OI"])

    def test_itm_contract_leaves_custom_maximum_blank(self):
        row = self.evaluate(replace(self.quote, strike=101, ask=2))
        self.assertIsNone(row["最大到期跌幅"])
        self.assertIn("K > S", row["篩選原因"])
        self.assertEqual(row["跌 20% 組合損益"], -100)

    def test_inverted_quote_excludes_cost_simulation(self):
        row = self.evaluate(replace(self.quote, bid=2.5))
        self.assertIn("Bid 高於 Ask", row["篩選原因"])
        self.assertIsNone(row["跌 20% 組合損益"])


if __name__ == "__main__":
    unittest.main()
