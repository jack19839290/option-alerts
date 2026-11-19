import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.models import ChainSnapshot, OptionQuote
from app.provider import MarketDataError
from long_call.scan import scan
from long_call.screen import Thresholds, evaluate
from long_call.sheet import SCHEMA


class LongCallTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 19, 21, 26, tzinfo=timezone.utc)
        expiry = self.now.date() + timedelta(days=180)
        self.thresholds = Thresholds.from_cells(SCHEMA["defaults"])
        self.chain = ChainSnapshot("TEST", expiry, 100, 0)
        self.quote = OptionQuote(
            f"TEST{expiry:%y%m%d}C00055000", "CALL", 55, None,
            46.6, 47.4, 0.25, 3, 500, None, "REGULAR",
        )

    def evaluate(self, source="Mid", quote=None):
        return evaluate(self.chain, quote or self.quote, replace(self.thresholds, price_source=source),
                        self.now, self.now, 0.04)

    def test_buy_price_basis_and_cent_limit(self):
        result = self.evaluate()
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.row[7], 0.53)
        self.assertAlmostEqual(result.row[8], 2 / 53 * 365 / 180)
        self.assertEqual(result.row[9], 47.08)
        self.assertTrue(self.evaluate("Bid").passed)
        self.assertFalse(self.evaluate("Ask").passed)
        for price, passed in ((47.08, True), (47.09, False)):
            self.assertEqual(self.evaluate(quote=replace(self.quote, bid=price, ask=price)).passed, passed)

    def test_invalid_quotes_and_missing_data(self):
        for quote in [
            replace(self.quote, bid=0),
            replace(self.quote, ask=46),
            replace(self.quote, bid=44.9, ask=45),
            replace(self.quote, open_interest=None),
            replace(self.quote, implied_volatility=None),
            replace(self.quote, contract_symbol="TEST1" + self.quote.contract_symbol[4:]),
        ]:
            self.assertFalse(self.evaluate(quote=quote).passed)

    def test_scan_includes_both_dte_boundaries_and_records_partial(self):
        dates = [self.now.date() + timedelta(days=days) for days in (89, 90, 270, 271)]
        test = self

        class Provider:
            risk_free_rate_note = ""
            queried = []

            def fetch_risk_free_rate(self, *_):
                return 0.04

            def fetch_expirations(self, ticker):
                return dates

            def fetch_chain(self, ticker, expiry, *, calls_only):
                self.queried.append((expiry, calls_only))
                if expiry == dates[2]:
                    raise MarketDataError("行情缺漏")
                quote = replace(test.quote, contract_symbol=f"TEST{expiry:%y%m%d}C00055000")
                return ChainSnapshot(ticker, expiry, 100, 0, [quote])

        class Sheet:
            def read(self, *_):
                return [SCHEMA["logs"]]

            def load_targets(self):
                return {"TEST": test.thresholds}, []

            def publish(self, results, detail, log, count):
                self.log = log
                self.detail = detail

        provider, sheet = Provider(), Sheet()
        self.assertEqual(scan(sheet, close=True, now=self.now, provider=provider), 1)
        self.assertEqual(provider.queried, [(dates[1], True), (dates[2], True)])
        self.assertEqual(sheet.log[3:7], ["部分完成", 1, 2, 1])
        self.assertEqual(sheet.log[9], "待寄")
        self.assertEqual(sheet.detail[0][2], 90)
