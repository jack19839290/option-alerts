import unittest

from app.pricing import (
    annualized_premium_return,
    bid_ask_spread_rate,
    calculate_mid,
    select_alert_price,
    select_seller_price,
)


class PricingTests(unittest.TestCase):
    def test_mid_is_preferred_for_legacy_display_price(self):
        price, source, midpoint = select_alert_price(2.0, 2.4, 2.3)
        self.assertAlmostEqual(price, 2.2)
        self.assertEqual(source, "Mid")
        self.assertAlmostEqual(midpoint, 2.2)

    def test_seller_price_uses_only_valid_bid(self):
        self.assertEqual(select_seller_price(2.0), (2.0, "Bid"))
        self.assertEqual(select_seller_price(0), (None, "Bid無效"))
        self.assertIsNone(calculate_mid(2.4, 2.0))

    def test_bid_ask_spread_rate_uses_mid(self):
        self.assertAlmostEqual(bid_ask_spread_rate(3.8, 4.2), 0.10)
        self.assertIsNone(bid_ask_spread_rate(0, 4.2))
        self.assertIsNone(bid_ask_spread_rate(4.2, 3.8))

    def test_annualized_return_formula(self):
        result = annualized_premium_return(
            seller_premium=1.0, capital_basis=50.0, dte=30
        )
        self.assertAlmostEqual(result, 1 / 50 / 30 * 365)

    def test_annualized_return_requires_bid_capital_and_positive_dte(self):
        self.assertIsNone(
            annualized_premium_return(
                seller_premium=None, capital_basis=50.0, dte=30
            )
        )
        self.assertIsNone(
            annualized_premium_return(
                seller_premium=1.0, capital_basis=None, dte=30
            )
        )
        self.assertIsNone(
            annualized_premium_return(
                seller_premium=1.0, capital_basis=50.0, dte=0
            )
        )


if __name__ == "__main__":
    unittest.main()
