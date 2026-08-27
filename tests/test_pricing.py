import unittest

from app.pricing import select_alert_price


class PricingTests(unittest.TestCase):
    def test_mid_is_preferred(self):
        price, source, midpoint = select_alert_price(2.0, 2.4, 2.3)
        self.assertAlmostEqual(price, 2.2)
        self.assertEqual(source, "Mid")
        self.assertAlmostEqual(midpoint, 2.2)

    def test_last_is_fallback(self):
        price, source, midpoint = select_alert_price(0, None, 2.3)
        self.assertEqual(price, 2.3)
        self.assertEqual(source, "Last")
        self.assertIsNone(midpoint)

    def test_invalid_market_has_no_price(self):
        price, source, midpoint = select_alert_price(None, None, None)
        self.assertIsNone(price)
        self.assertEqual(source, "無可用價格")
        self.assertIsNone(midpoint)


if __name__ == "__main__":
    unittest.main()

