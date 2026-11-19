import json
import re
from decimal import InvalidOperation
from pathlib import Path

from app.models import as_bool
from app.sheets import SheetsRepository

from .screen import Thresholds

SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text(encoding="utf-8"))


def row_data(row):
    cells = []
    for value in row:
        if value is None:
            cells.append({})
        elif isinstance(value, (int, float)):
            cells.append({"userEnteredValue": {"numberValue": value}})
        else:
            cells.append({"userEnteredValue": {"stringValue": str(value)}})
    return {"values": cells}


class LongCallSheet:
    def __init__(self, spreadsheet_id):
        self.id = spreadsheet_id
        self.api = SheetsRepository(spreadsheet_id).service.spreadsheets()
        response = self.api.get(
            spreadsheetId=self.id, fields="sheets(properties(sheetId,title,gridProperties)"
            ",basicFilter)"
        ).execute(num_retries=3)
        self.tabs = {tab["properties"]["title"]: tab for tab in response["sheets"]}
        if not {SCHEMA[key] for key in ("settings", "results", "detail", "log")} <= self.tabs.keys():
            raise ValueError("試算表缺少買入買權專用分頁")
        ranges = [f"'{SCHEMA[key]}'!A1:{end}" for key, end in (
            ("results", "U1"), ("detail", "U1"), ("log", "L1"),
        )]
        headers = self.api.values().batchGet(spreadsheetId=self.id, ranges=ranges).execute(num_retries=3)
        expected = [SCHEMA["contracts"], SCHEMA["contracts"], SCHEMA["logs"]]
        if [item.get("values", [[]])[0] for item in headers["valueRanges"]] != expected:
            raise ValueError("買入買權分頁的欄位名稱或順序不符")

    def read(self, key, ranges):
        return self.api.values().get(
            spreadsheetId=self.id, range=f"'{SCHEMA[key]}'!{ranges}",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute(num_retries=3).get("values", [])

    def load_targets(self):
        entries = self.read("settings", "A5:J")
        defaults = (entries[0][2:] + [""] * 8)[:8] if entries else [""] * 8
        Thresholds.from_cells(defaults)
        targets, errors = {}, []
        for row_number, row in enumerate(entries[5:], 10):
            if not row or not as_bool(row[0]):
                continue
            row = (row + [""] * 10)[:10]
            ticker = str(row[1]).strip().upper()
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,11}", ticker):
                errors.append(f"第 {row_number} 列：股票代號無效")
                continue
            if ticker in targets:
                errors.append(f"第 {row_number} 列：{ticker} 重複啟用")
                continue
            try:
                targets[ticker] = Thresholds.from_cells([
                    base if override == "" else override for base, override in zip(defaults, row[2:])
                ])
            except (ValueError, InvalidOperation) as exc:
                description = "門檻需輸入數字或百分比" if isinstance(exc, InvalidOperation) else str(exc)
                errors.append(f"第 {row_number} 列 {ticker}：{description}")
        return targets, errors

    def publish(self, results, details, log_entry, log_count):
        requests = []
        for key, rows in (("results", results), ("detail", details), ("log", [log_entry])):
            tab = self.tabs[SCHEMA[key]]
            props = tab["properties"]
            tab_id = props["sheetId"]
            height = props["gridProperties"]["rowCount"]
            start = log_count if key == "log" else 1
            needed = start + len(rows)
            if needed > height:
                requests.append({"appendDimension": {
                    "sheetId": tab_id, "dimension": "ROWS", "length": needed - height,
                }})
            if key == "log":
                requests.append({"updateCells": {
                    "start": {"sheetId": tab_id, "rowIndex": start, "columnIndex": 0},
                    "rows": [row_data(log_entry)], "fields": "userEnteredValue",
                }})
                continue
            width = len(SCHEMA["contracts"])
            requests.append({"updateCells": {
                "range": {"sheetId": tab_id, "startRowIndex": 1, "endRowIndex": max(height, needed),
                          "startColumnIndex": 0, "endColumnIndex": width},
                "rows": [row_data(row) for row in rows], "fields": "userEnteredValue",
            }})
            for start_col, end_col, kind, pattern in (
                (6, 9, "PERCENT", "0.00%"), (9, 10, "NUMBER", "0.00"),
            ):
                requests.append({"repeatCell": {
                    "range": {"sheetId": tab_id, "startRowIndex": 1, "endRowIndex": max(2, needed),
                              "startColumnIndex": start_col, "endColumnIndex": end_col},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": kind, "pattern": pattern}}},
                    "fields": "userEnteredFormat.numberFormat",
                }})
            existing = tab.get("basicFilter", {}).copy()
            existing["range"] = {
                "sheetId": tab_id, "startRowIndex": 0, "endRowIndex": max(2, needed),
                "startColumnIndex": 0, "endColumnIndex": width,
            }
            requests.append({"setBasicFilter": {"filter": existing}})
        self.api.batchUpdate(spreadsheetId=self.id, body={"requests": requests}).execute(num_retries=0)
