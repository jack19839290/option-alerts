from __future__ import annotations

from datetime import datetime
from typing import Any

from .constants import (
    CONTRACT_HEADERS,
    MONITOR_HEADERS,
    MONITOR_SHEET,
    OUTPUT_HEADERS,
    SETTINGS_DEFAULTS,
    SETTINGS_SHEET,
    SYSTEM_LOG_SHEET,
)
from .models import MonitorRecord


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_range(sheet_name: str, cell_range: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'!{cell_range}"


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

    def load_monitors(self) -> tuple[list[str], list[MonitorRecord], list[dict[str, Any]]]:
        end_col = _column_name(len(MONITOR_HEADERS))
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(MONITOR_SHEET, f"A1:{end_col}{self.max_monitor_rows}"),
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            )
            .execute()
        )
        values = response.get("values", [])
        if not values:
            raise RuntimeError("監控清單缺少標題列")
        headers = [str(value) for value in values[0]]
        missing = [header for header in MONITOR_HEADERS if header not in headers]
        if missing:
            raise RuntimeError(f"監控清單缺少欄位: {', '.join(missing)}")

        monitors: list[MonitorRecord] = []
        invalid: list[dict[str, Any]] = []
        for row_number, row in enumerate(values[1:], start=2):
            if not any(str(value).strip() for value in row):
                continue
            try:
                monitors.append(MonitorRecord.from_values(row_number, headers, row))
            except ValueError as exc:
                invalid.append({"row_number": row_number, "error": str(exc)})
        return headers, monitors, invalid

    def update_monitor_outputs(
        self,
        headers: list[str],
        monitors: list[MonitorRecord],
        updates: dict[str, dict[str, Any]],
    ) -> None:
        if not monitors:
            return
        output_start = headers.index(OUTPUT_HEADERS[0]) + 1
        output_end = output_start + len(OUTPUT_HEADERS) - 1
        data = []
        for monitor in monitors:
            row_update = updates.get(monitor.monitor_id)
            if row_update is None:
                continue
            merged = dict(monitor.values)
            merged.update(row_update)
            row_values = [[self._serializable(merged.get(header, "")) for header in OUTPUT_HEADERS]]
            data.append(
                {
                    "range": _sheet_range(
                        MONITOR_SHEET,
                        f"{_column_name(output_start)}{monitor.row_number}:"
                        f"{_column_name(output_end)}{monitor.row_number}",
                    ),
                    "values": row_values,
                }
            )
        if data:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute()

    def write_contract_sheets(
        self,
        monitors: list[MonitorRecord],
        updates: dict[str, dict[str, Any]],
    ) -> None:
        grouped: dict[str, list[MonitorRecord]] = {}
        for monitor in monitors:
            grouped.setdefault(monitor.sheet_name, []).append(monitor)
        self._ensure_sheets(list(grouped))

        data: list[dict[str, Any]] = []
        clear_ranges: list[str] = []
        for sheet_name, sheet_monitors in grouped.items():
            rows = [CONTRACT_HEADERS]
            for monitor in sorted(
                sheet_monitors, key=lambda item: (item.strike, item.option_type)
            ):
                merged = dict(monitor.values)
                merged.update(updates.get(monitor.monitor_id, {}))
                merged["監控ID"] = monitor.monitor_id
                merged["啟用"] = monitor.enabled
                merged["類型"] = monitor.option_type
                merged["履約價"] = monitor.strike
                merged["低於警示"] = monitor.low_threshold or ""
                merged["高於警示"] = monitor.high_threshold or ""
                rows.append(
                    [self._serializable(merged.get(header, "")) for header in CONTRACT_HEADERS]
                )
            end_col = _column_name(len(CONTRACT_HEADERS))
            clear_ranges.append(
                _sheet_range(sheet_name, f"A2:{end_col}{self.max_monitor_rows}")
            )
            data.append(
                {
                    "range": _sheet_range(sheet_name, f"A1:{end_col}{len(rows)}"),
                    "values": rows,
                }
            )
        if clear_ranges:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id,
                body={"ranges": clear_ranges},
            ).execute()
        if data:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
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

    def _ensure_sheets(self, titles: list[str]) -> None:
        metadata = (
            self.service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        existing = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
        requests = [
            {
                "addSheet": {
                    "properties": {
                        "title": title,
                        "gridProperties": {"frozenRowCount": 1},
                    }
                }
            }
            for title in titles
            if title not in existing
        ]
        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": requests}
            ).execute()

    @staticmethod
    def _serializable(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        return value
