import unittest
from datetime import date, datetime, timezone

from app.lookup_expirations import lookup
from app.provider import MarketDataError


class FakeRepository:
    def __init__(self):
        self.records = []

    def store_expiration_lookup(self, **record):
        self.records.append(record)
        return True


class FakeProvider:
    def __init__(self, expirations=None, error=None):
        self.expirations = expirations or []
        self.error = error

    def fetch_expirations(self, ticker):
        if self.error:
            raise self.error
        return self.expirations


class LookupJobTests(unittest.TestCase):
    def test_success_is_written_for_the_matching_request(self):
        repository = FakeRepository()
        result = lookup(
            "MU",
            "request-1",
            repository,
            FakeProvider([date(2026, 12, 18), date(2027, 3, 19)]),
            now=datetime(2026, 9, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(repository.records[0]["status"], "SUCCESS")
        self.assertEqual(repository.records[0]["request_id"], "request-1")

    def test_expected_yahoo_failure_is_written_for_the_dialog(self):
        repository = FakeRepository()
        result = lookup(
            "BAD",
            "request-2",
            repository,
            FakeProvider(error=MarketDataError("沒有到期日")),
            now=datetime(2026, 9, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(repository.records[0]["status"], "FAILED")
        self.assertIn("沒有到期日", repository.records[0]["error"])


if __name__ == "__main__":
    unittest.main()
