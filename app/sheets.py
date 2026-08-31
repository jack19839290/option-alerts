from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .constants import (
    CHAIN_HEADERS,
    CLOSE_TREND_HEADERS,
    CLOSE_TREND_SHEET,
    SCAN_HEADERS,
    SCAN_OUTPUT_HEADERS,
    SCAN_SHEET,
    SETTINGS_DEFAULTS,
    SETTINGS_SHEET,
    SYSTEM_LOG_SHEET,
)
from .models import ScanRecord


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_range(sheet_name: str, cell_range: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'!{cell_range}"


def _is_blank_scan_row(headers: list[str], row: list[Any]) -> bool:
    """Ignore placeholder checkbox values on otherwise empty scan rows."""
    padded = row + [""] * max(0, len(headers) - len(row))
    values = dict(zip(headers, padded))
    meaningful_headers = [
        header
        for header in SCAN_HEADERS[:15]
        if header not in {"啟用", "Email通知"}
    ]
    return not any(
        value not in (None, "") for value in (values.get(header) for header in meaningful_headers)
    )


class SheetsRepository:
    def __init__(self, spreadsheet_id: str, max_monitor_rows: int = 1000):
        from google.auth import default
        from googleapiclient.discovery import build

        credentials, _ = default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.spreadsheet_id = spreadsheet_id
        self.max_monitor_rows = max_monitor_rows
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def load_settings(self) -> dict[str, Any]:
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(SETTINGS_SHEET, "A2:B40"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
        settings = dict(SETTINGS_DEFAULTS)
        for row in response.get("values", []):
            if len(row) >= 2 and str(row[0]).strip():
                settings[str(row[0]).strip()] = row[1]
        return settings

    def update_settings(self, updates: dict[str, Any]) -> None:
        if not updates:
            return
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(SETTINGS_SHEET, "A2:B40"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
        rows = response.get("values", [])
        ranges = []
        for offset, row in enumerate(rows, start=2):
            if row and str(row[0]).strip() in updates:
                ranges.append(
                    {
                        "range": _sheet_range(SETTINGS_SHEET, f"B{offset}"),
                        "values": [[updates[str(row[0]).strip()]]],
                    }
                )
        if ranges:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": ranges},
            ).execute()

    def load_scans(self) -> tuple[list[str], list[ScanRecord], list[dict[str, Any]]]:
        end_col = _column_name(len(SCAN_HEADERS))
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(SCAN_SHEET, f"A1:{end_col}{self.max_monitor_rows}"),
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            )
            .execute()
        )
        values = response.get("values", [])
        if not values:
            raise RuntimeError("掃描設定缺少標題列")
        headers = [str(value) for value in values[0]]
        missing = [header for header in SCAN_HEADERS if header not in headers]
        if missing:
            raise RuntimeError(f"掃描設定缺少欄位: {', '.join(missing)}")

        scans: list[ScanRecord] = []
        invalid: list[dict[str, Any]] = []
        for row_number, row in enumerate(values[1:], start=2):
            if _is_blank_scan_row(headers, row):
                continue
            try:
                scans.append(ScanRecord.from_values(row_number, headers, row))
            except ValueError as exc:
                invalid.append({"row_number": row_number, "error": str(exc)})
        return headers, scans, invalid

    def load_chain_states(
        self, scans: list[ScanRecord]
    ) -> dict[str, dict[str, dict[str, Any]]]:
        if not scans:
            return {}
        self._ensure_sheets(
            [scan.sheet_name for scan in scans], min_columns=len(CHAIN_HEADERS)
        )
        end_col = _column_name(len(CHAIN_HEADERS))
        ranges = [
            _sheet_range(scan.sheet_name, f"A1:{end_col}{self.max_monitor_rows}")
            for scan in scans
        ]
        response = (
            self.service.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=self.spreadsheet_id,
                ranges=ranges,
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            )
            .execute()
        )
        result: dict[str, dict[str, dict[str, Any]]] = {}
        value_ranges = response.get("valueRanges", [])
        for scan, value_range in zip(scans, value_ranges):
            values = value_range.get("values", [])
            states: dict[str, dict[str, Any]] = {}
            if values:
                headers = [str(value) for value in values[0]]
                for row in values[1:]:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    mapped = dict(zip(headers, padded))
                    symbol = str(mapped.get("合約代號") or "").strip()
                    if symbol and str(mapped.get("掃描ID") or "") == scan.scan_id:
                        states[symbol] = mapped
            result[scan.scan_id] = states
        return result

    def update_scan_outputs(
        self,
        headers: list[str],
        scans: list[ScanRecord],
        updates: dict[str, dict[str, Any]],
    ) -> None:
        if not scans:
            return
        output_start = headers.index(SCAN_OUTPUT_HEADERS[0]) + 1
        output_end = output_start + len(SCAN_OUTPUT_HEADERS) - 1
        data = []
        for scan in scans:
            row_update = updates.get(scan.scan_id)
            if row_update is None:
                continue
            merged = dict(scan.values)
            merged.update(row_update)
            row_values = [
                [self._serializable(merged.get(header, "")) for header in SCAN_OUTPUT_HEADERS]
            ]
            data.append(
                {
                    "range": _sheet_range(
                        SCAN_SHEET,
                        f"{_column_name(output_start)}{scan.row_number}:"
                        f"{_column_name(output_end)}{scan.row_number}",
                    ),
                    "values": row_values,
                }
            )
        if data:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute()

    def write_chain_sheets(
        self,
        scans: list[ScanRecord],
        chain_rows: dict[str, list[dict[str, Any]]],
    ) -> None:
        targets = [scan for scan in scans if scan.scan_id in chain_rows]
        if not targets:
            return
        self._ensure_sheets(
            [scan.sheet_name for scan in targets], min_columns=len(CHAIN_HEADERS)
        )
        data: list[dict[str, Any]] = []
        clear_ranges: list[str] = []
        end_col = _column_name(len(CHAIN_HEADERS))
        for scan in targets:
            rows = [CHAIN_HEADERS]
            for values in chain_rows[scan.scan_id]:
                rows.append(
                    [self._serializable(values.get(header, "")) for header in CHAIN_HEADERS]
                )
            clear_ranges.append(
                _sheet_range(scan.sheet_name, f"A2:{end_col}{self.max_monitor_rows}")
            )
            data.append(
                {
                    "range": _sheet_range(scan.sheet_name, f"A1:{end_col}{len(rows)}"),
                    "values": rows,
                }
            )
        self.service.spreadsheets().values().batchClear(
            spreadsheetId=self.spreadsheet_id,
            body={"ranges": clear_ranges},
        ).execute()
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()

    def upsert_close_trend_rows(self, rows: list[dict[str, Any]]) -> None:
        """Write one immutable successful close snapshot per daily snapshot ID.

        Failed or incomplete placeholders may be replaced by a later successful retry,
        while an already selected contract is left unchanged.
        """
        if not rows:
            return
        self._ensure_sheets(
            [CLOSE_TREND_SHEET], min_columns=len(CLOSE_TREND_HEADERS)
        )
        end_col = _column_name(len(CLOSE_TREND_HEADERS))
        header_response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_TREND_SHEET, f"A1:{end_col}1"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
        header_values = header_response.get("values", [])
        if not header_values or not any(header_values[0]):
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_TREND_SHEET, f"A1:{end_col}1"),
                valueInputOption="RAW",
                body={"values": [CLOSE_TREND_HEADERS]},
            ).execute()
        else:
            existing_headers = [str(value) for value in header_values[0]]
            if existing_headers != CLOSE_TREND_HEADERS:
                raise RuntimeError("收盤Delta趨勢欄位與目前版本不一致，請先執行初始化／升級系統")

        existing_response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_TREND_SHEET, "A2:J"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
        existing: dict[str, tuple[int, str]] = {}
        for row_number, values in enumerate(existing_response.get("values", []), start=2):
            snapshot_id = str(values[0] if values else "").strip()
            if not snapshot_id or snapshot_id in existing:
                continue
            status = str(values[9] if len(values) > 9 else "").strip()
            existing[snapshot_id] = (row_number, status)

        updates: list[dict[str, Any]] = []
        appends: list[list[Any]] = []
        seen_input: set[str] = set()
        for values in rows:
            snapshot_id = str(values.get("快照ID") or "").strip()
            if not snapshot_id or snapshot_id in seen_input:
                continue
            seen_input.add(snapshot_id)
            row_values = [
                self._serializable(values.get(header, ""))
                for header in CLOSE_TREND_HEADERS
            ]
            prior = existing.get(snapshot_id)
            if prior is None:
                appends.append(row_values)
                continue
            row_number, prior_status = prior
            if prior_status == "已選取":
                continue
            updates.append(
                {
                    "range": _sheet_range(
                        CLOSE_TREND_SHEET, f"A{row_number}:{end_col}{row_number}"
                    ),
                    "values": [row_values],
                }
            )

        if updates:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": updates},
            ).execute()
        if appends:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_TREND_SHEET, f"A:{end_col}"),
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": appends},
            ).execute()

    def append_system_log(self, level: str, message: str, details: str = "") -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=_sheet_range(SYSTEM_LOG_SHEET, "A:D"),
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={
                "values": [
                    [
                        datetime.utcnow().isoformat(timespec="seconds") + "Z",
                        level,
                        message,
                        details[:5000],
                    ]
                ]
            },
        ).execute()

    def _ensure_sheets(self, titles: list[str], min_columns: int = 26) -> None:
        metadata = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets.properties(sheetId,title,gridProperties(columnCount))",
            )
            .execute()
        )
        existing = {
            sheet["properties"]["title"]: sheet["properties"]
            for sheet in metadata.get("sheets", [])
        }
        requests: list[dict[str, Any]] = []
        for title in dict.fromkeys(titles):
            properties = existing.get(title)
            if properties is None:
                requests.append(
                    {
                        "addSheet": {
                            "properties": {
                                "title": title,
                                "gridProperties": {
                                    "frozenRowCount": 1,
                                    "columnCount": max(26, min_columns),
                                },
                            }
                        }
                    }
                )
                continue
            column_count = int(
                properties.get("gridProperties", {}).get("columnCount", 0) or 0
            )
            if column_count < min_columns:
                requests.append(
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": properties["sheetId"],
                                "gridProperties": {"columnCount": min_columns},
                            },
                            "fields": "gridProperties.columnCount",
                        }
                    }
                )
        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": requests}
            ).execute()

    @staticmethod
    def _serializable(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value
