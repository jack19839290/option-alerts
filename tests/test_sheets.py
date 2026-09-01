import unittest
from datetime import datetime, timedelta, timezone

from app.constants import CLOSE_TREND_HEADERS, SCAN_HEADERS
from app.sheets import SheetsRepository, _is_blank_scan_row


class FakeRequest:
    def __init__(self, response=None):
        self.response = response or {}

    def execute(self):
        return self.response


class FakeValuesApi:
    def __init__(self, existing_rows):
        self.existing_rows = existing_rows
        self.batch_updates = []
        self.appends = []
        self.updates = []

    def get(self, **kwargs):
        target = kwargs["range"]
        if target.endswith("A1:AN1"):
            return FakeRequest({"values": [CLOSE_TREND_HEADERS]})
        if target.endswith("A2:J"):
            return FakeRequest({"values": self.existing_rows})
        raise AssertionError(f"unexpected range: {target}")

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return FakeRequest()

    def batchUpdate(self, **kwargs):
        self.batch_updates.append(kwargs)
        return FakeRequest()

    def append(self, **kwargs):
        self.appends.append(kwargs)
        return FakeRequest()


class FakeSpreadsheetsApi:
    def __init__(self, existing_rows):
        self.values_api = FakeValuesApi(existing_rows)
        self.sheet_updates = []

    def values(self):
        return self.values_api

    def get(self, **kwargs):
        return FakeRequest(
            {
                "sheets": [
                    {
                        "properties": {
                            "sheetId": 123,
                            "title": "收盤Delta趨勢",
                            "gridProperties": {"columnCount": 40},
                        }
                    }
                ]
            }
        )

    def batchUpdate(self, **kwargs):
        self.sheet_updates.append(kwargs)
        return FakeRequest()


class FakeService:
    def __init__(self, existing_rows):
        self.spreadsheets_api = FakeSpreadsheetsApi(existing_rows)

    def spreadsheets(self):
        return self.spreadsheets_api


def make_repository(existing_rows):
    repository = object.__new__(SheetsRepository)
    repository.spreadsheet_id = "spreadsheet-id"
    repository.max_monitor_rows = 1000
    repository.service = FakeService(existing_rows)
    return repository


class ScanRowTests(unittest.TestCase):
    def test_unchecked_checkbox_placeholders_are_blank(self):
        row = [False] + [""] * 12 + [False]

        self.assertTrue(_is_blank_scan_row(SCAN_HEADERS, row))

    def test_configured_scan_is_not_blank(self):
        row = [False, "MU|2027-01-15", "MU", "2027-01-15", "ALL"]

        self.assertFalse(_is_blank_scan_row(SCAN_HEADERS, row))


class TimestampSerializationTests(unittest.TestCase):
    def test_user_facing_timestamp_uses_taipei_wall_clock(self):
        repository = object.__new__(SheetsRepository)
        repository.display_timezone = "Asia/Taipei"
        source = datetime(2026, 9, 1, 15, 3, 46, tzinfo=timezone.utc)

        serial = repository._serializable(source, "最後抓取時間")
        displayed = datetime(1899, 12, 30) + timedelta(days=serial)

        self.assertEqual(displayed, datetime(2026, 9, 1, 23, 3, 46))

    def test_explicit_utc_timestamp_keeps_utc_wall_clock(self):
        repository = object.__new__(SheetsRepository)
        repository.display_timezone = "Asia/Taipei"
        source = datetime(2026, 9, 1, 15, 3, 46, tzinfo=timezone.utc)

        serial = repository._serializable(source, "實際抓取時間(UTC)")
        displayed = datetime(1899, 12, 30) + timedelta(days=serial)

        self.assertEqual(displayed, datetime(2026, 9, 1, 15, 3, 46))


class CloseTrendWriteTests(unittest.TestCase):
    def test_successful_snapshot_is_not_overwritten(self):
        snapshot_id = "2026-08-27|MU|2027-01-15|PUT|0.10"
        existing = [[snapshot_id, "2026-08-27", "", "", "", "", "", "PUT", 0.1, "已選取"]]
        repository = make_repository(existing)
        repository.upsert_close_trend_rows(
            [{"快照ID": snapshot_id, "選取狀態": "已選取", "履約價": 55}]
        )
        values_api = repository.service.spreadsheets_api.values_api
        self.assertEqual(values_api.batch_updates, [])
        self.assertEqual(values_api.appends, [])

    def test_failed_placeholder_is_replaced_and_new_snapshot_is_appended(self):
        failed_id = "2026-08-27|MU|2027-01-15|PUT|0.10"
        new_id = "2026-08-27|MU|2027-01-15|PUT|0.15"
        existing = [[failed_id, "2026-08-27", "", "", "", "", "", "PUT", 0.1, "抓取失敗"]]
        repository = make_repository(existing)
        repository.upsert_close_trend_rows(
            [
                {"快照ID": failed_id, "選取狀態": "已選取", "履約價": 55},
                {"快照ID": new_id, "選取狀態": "無符合合約"},
            ]
        )
        values_api = repository.service.spreadsheets_api.values_api
        self.assertEqual(len(values_api.batch_updates), 1)
        self.assertEqual(len(values_api.batch_updates[0]["body"]["data"]), 1)
        self.assertEqual(len(values_api.appends), 1)
        self.assertEqual(len(values_api.appends[0]["body"]["values"]), 1)


if __name__ == "__main__":
    unittest.main()
