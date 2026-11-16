from __future__ import annotations

import json
import hashlib
import time
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .constants import (
    CHAIN_HEADERS,
    CLOSE_ALERT_STATE_HEADERS,
    CLOSE_ALERT_STATE_SHEET,
    CLOSE_TREND_HEADERS,
    CLOSE_TREND_SHEET,
    EXPIRATION_CACHE_HEADERS,
    EXPIRATION_CACHE_SHEET,
    NOTIFICATION_QUEUE_HEADERS,
    NOTIFICATION_QUEUE_SHEET,
    NOTIFICATION_PAYLOAD_SHEET,
    NOTIFICATION_PAYLOAD_HEADERS,
    SCAN_HEADERS,
    SCAN_OUTPUT_HEADERS,
    SCAN_SHEET,
    SETTINGS_DEFAULTS,
    SETTINGS_SHEET,
    SYSTEM_LOG_SHEET,
    VOLATILITY_TREND_SHEET,
    VOLATILITY_TREND_HEADERS,
)
from .models import ScanRecord
from .rolling_repository import RollingRepositoryMixin


SHEETS_DATETIME_EPOCH = datetime(1899, 12, 30)


def _valid_timezone_name(value: Any, fallback: str = "Asia/Taipei") -> str:
    name = str(value or "").strip() or fallback
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return fallback
    return name


def _datetime_to_sheet_serial(value: datetime, timezone_name: str) -> float:
    """Convert an instant to a Google Sheets serial using the target wall-clock time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local_value = value.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
    return (local_value - SHEETS_DATETIME_EPOCH).total_seconds() / 86400


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
        for header in SCAN_HEADERS[:24]
        if header not in {"啟用", "第一門檻啟用", "第二門檻啟用", "Email通知"}
    ]
    return not any(
        value not in (None, "") for value in (values.get(header) for header in meaningful_headers)
    )


class SheetsRepository(RollingRepositoryMixin):
    def __init__(self, spreadsheet_id: str, max_monitor_rows: int = 1000):
        from google.auth import default
        from googleapiclient.discovery import build

        credentials, _ = default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.spreadsheet_id = spreadsheet_id
        self.max_monitor_rows = max_monitor_rows
        self.display_timezone = "Asia/Taipei"
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._verified_headers: set[tuple[str, tuple[str, ...]]] = set()
        self._sheet_properties_cache: dict[str, dict[str, Any]] | None = None

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
        self.display_timezone = _valid_timezone_name(settings.get("顯示時區"))
        settings["顯示時區"] = self.display_timezone
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
                [
                    self._serializable(merged.get(header, ""), header)
                    for header in SCAN_OUTPUT_HEADERS
                ]
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
        stale_tail_ranges: list[str] = []
        end_col = _column_name(len(CHAIN_HEADERS))
        for scan in targets:
            rows = [CHAIN_HEADERS]
            for values in chain_rows[scan.scan_id]:
                rows.append(
                    [
                        self._serializable(values.get(header, ""), header)
                        for header in CHAIN_HEADERS
                    ]
                )
            stale_start = len(rows) + 1
            if stale_start <= self.max_monitor_rows:
                stale_tail_ranges.append(
                    _sheet_range(scan.sheet_name, f"A{stale_start}:{end_col}{self.max_monitor_rows}")
                )
            data.append(
                {
                    "range": _sheet_range(scan.sheet_name, f"A1:{end_col}{len(rows)}"),
                    "values": rows,
                }
            )
        # Write the complete new snapshot first.  If this request fails, the previous
        # chain remains intact instead of leaving a blank worksheet.
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()
        if stale_tail_ranges:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id,
                body={"ranges": stale_tail_ranges},
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
            if existing_headers == CLOSE_TREND_HEADERS[:-2]:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=_sheet_range(CLOSE_TREND_SHEET, f"A1:{end_col}1"),
                    valueInputOption="RAW",
                    body={"values": [CLOSE_TREND_HEADERS]},
                ).execute()
                self._backfill_close_trend_differences()
            elif existing_headers != CLOSE_TREND_HEADERS:
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
                self._serializable(values.get(header, ""), header)
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

    def upsert_volatility_trend_rows(self, rows: list[dict[str, Any]]) -> None:
        """Preserve complete daily snapshots; replace incomplete rows on recovery."""
        if not rows:
            return
        name, headers = VOLATILITY_TREND_SHEET, VOLATILITY_TREND_HEADERS
        self._ensure_sheets([name], min_columns=len(headers))
        self._ensure_header(name, headers)
        api = self.service.spreadsheets().values()
        old = self._execute(api.get(spreadsheetId=self.spreadsheet_id,
            range=_sheet_range(name, "A2:P"), valueRenderOption="UNFORMATTED_VALUE"))
        existing = {str(row[15]): (i, row[11]) for i, row in enumerate(old.get("values", []), 2)
                    if len(row) >= 16 and row[15]}
        appends, updates, seen = [], [], set()
        for row in rows:
            key = row["快照ID"]
            if key in seen:
                continue
            seen.add(key)
            prior = existing.get(key)
            if prior and prior[1] == "正常":
                continue
            values = [self._serializable(row.get(h), h) for h in headers]
            if prior:
                updates.append({"range": _sheet_range(name, f"A{prior[0]}:P{prior[0]}"), "values": [values]})
            else:
                appends.append(values)
        if updates:
            self._execute(api.batchUpdate(spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "RAW", "data": updates}))
        if appends:
            self._execute(api.append(spreadsheetId=self.spreadsheet_id, range=_sheet_range(name, "A:P"),
                valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": appends}))

    def append_notification_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self._ensure_sheets([NOTIFICATION_QUEUE_SHEET], min_columns=len(NOTIFICATION_QUEUE_HEADERS))
        self._ensure_header(NOTIFICATION_QUEUE_SHEET, NOTIFICATION_QUEUE_HEADERS)
        end_col = _column_name(len(NOTIFICATION_QUEUE_HEADERS))
        existing_response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=_sheet_range(NOTIFICATION_QUEUE_SHEET, "A2:A"),
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        existing_ids = {str(row[0]) for row in existing_response.get("values", []) if row}
        rows: list[list[Any]] = []
        payload_chunks: list[list[Any]] = []
        for event in events:
            event_id = str(event.get("事件ID") or "").strip()
            if not event_id or event_id in existing_ids:
                continue
            existing_ids.add(event_id)
            values = dict(event)
            for name in ("失敗掃描", "內容JSON"):
                if isinstance(values.get(name), (dict, list)):
                    values[name] = json.dumps(values[name], ensure_ascii=False, separators=(",", ":"))
            payload = str(values.get("內容JSON") or "{}")
            if len(payload.encode("utf-16-le")) // 2 > 40000:
                payload_id = hashlib.sha256((event_id + "\n" + payload).encode("utf-8")).hexdigest()
                # ASCII escaping keeps each code point one UTF-16 unit, including emoji.
                encoded = json.dumps(json.loads(payload), ensure_ascii=True, separators=(",", ":"))
                chunks = [encoded[start:start + 40000] for start in range(0, len(encoded), 40000)]
                payload_chunks.extend([[payload_id, index, chunk] for index, chunk in enumerate(chunks)])
                values["內容JSON"] = json.dumps({"storage": "chunks-v1", "payload_id": payload_id,
                    "chunk_count": len(chunks), "length": len(encoded)}, separators=(",", ":"))
            rows.append([self._serializable(values.get(header, ""), header) for header in NOTIFICATION_QUEUE_HEADERS])
        # Persist chunks first. A failure leaves no sendable queue entry. Content-based IDs
        # make retries safe; readers accept identical orphan duplicates from an uncertain append.
        if payload_chunks:
            self._ensure_sheets([NOTIFICATION_PAYLOAD_SHEET], min_columns=len(NOTIFICATION_PAYLOAD_HEADERS))
            self._ensure_header(NOTIFICATION_PAYLOAD_SHEET, NOTIFICATION_PAYLOAD_HEADERS)
            self._execute(self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id, range=_sheet_range(NOTIFICATION_PAYLOAD_SHEET, "A:C"),
                valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": payload_chunks}))
        if rows:
            self._execute(self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(NOTIFICATION_QUEUE_SHEET, f"A:{end_col}"),
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ))

    def _backfill_close_trend_differences(self) -> None:
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=_sheet_range(CLOSE_TREND_SHEET, "L2:P"),
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        updates: list[list[Any]] = []
        for row in response.get("values", []):
            strike = row[0] if len(row) > 0 else None
            spot = row[4] if len(row) > 4 else None
            try:
                difference = float(spot) - float(strike)
                rate = difference / float(spot) if float(spot) != 0 else ""
                updates.append([difference, rate])
            except (TypeError, ValueError):
                updates.append(["", ""])
        if updates:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_TREND_SHEET, f"AO2:AP{len(updates) + 1}"),
                valueInputOption="RAW",
                body={"values": updates},
            ).execute()

    def load_close_history(
        self, market_date: str
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        """Load today's state and the latest prior success for every scan in one read."""
        if not market_date:
            return {}, {}
        self._ensure_sheets([CLOSE_ALERT_STATE_SHEET], min_columns=len(CLOSE_ALERT_STATE_HEADERS))
        self._ensure_header(CLOSE_ALERT_STATE_SHEET, CLOSE_ALERT_STATE_HEADERS)
        response = self._execute(
            self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(CLOSE_ALERT_STATE_SHEET, "A2:J"),
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            )
        )
        current: dict[str, dict[str, Any]] = {}
        previous: dict[str, dict[str, Any]] = {}
        for row in response.get("values", []):
            padded = row + [""] * (len(CLOSE_ALERT_STATE_HEADERS) - len(row))
            mapped = dict(zip(CLOSE_ALERT_STATE_HEADERS, padded))
            scan_id = str(mapped.get("掃描ID") or "")
            record_date = str(mapped.get("美東交易日") or "")
            if not scan_id or not record_date:
                continue
            if record_date == market_date:
                current[scan_id] = mapped
                continue
            if record_date >= market_date or str(mapped.get("狀態")) != "SUCCESS":
                continue
            prior = previous.get(scan_id)
            if prior and str(prior.get("market_date") or "") >= record_date:
                continue
            try:
                symbols = json.loads(str(mapped.get("符合合約JSON") or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                symbols = []
            previous[scan_id] = {
                "market_date": record_date,
                "fingerprint": mapped.get("第一條件指紋"),
                "symbols": symbols if isinstance(symbols, list) else [],
            }
        return current, previous

    def load_close_records(self, market_date: str) -> dict[str, dict[str, Any]]:
        current, _ = self.load_close_history(market_date)
        return current

    def load_previous_close_record(self, scan_id: str, market_date: str) -> dict[str, Any] | None:
        _, previous = self.load_close_history(market_date)
        return previous.get(scan_id)

    def upsert_close_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self._ensure_sheets([CLOSE_ALERT_STATE_SHEET], min_columns=len(CLOSE_ALERT_STATE_HEADERS))
        self._ensure_header(CLOSE_ALERT_STATE_SHEET, CLOSE_ALERT_STATE_HEADERS)
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=_sheet_range(CLOSE_ALERT_STATE_SHEET, "A2:J"),
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        existing = {
            str(row[0]): (index, row)
            for index, row in enumerate(response.get("values", []), start=2)
            if row
        }
        end_col = _column_name(len(CLOSE_ALERT_STATE_HEADERS))
        updates: list[dict[str, Any]] = []
        appends: list[list[Any]] = []
        for record in records:
            previous = existing.get(str(record.get("record_id")))
            previous_row = previous[1] if previous else []
            previous_attempts = 0
            if len(previous_row) >= len(CLOSE_ALERT_STATE_HEADERS):
                try:
                    previous_attempts = int(float(previous_row[CLOSE_ALERT_STATE_HEADERS.index("嘗試次數")]))
                except (TypeError, ValueError):
                    previous_attempts = 0
            mapped = {
                "記錄ID": record.get("record_id"), "美東交易日": record.get("market_date"),
                "掃描ID": record.get("scan_id"), "第一條件指紋": record.get("fingerprint"),
                "狀態": record.get("status"),
                "符合合約JSON": json.dumps(record.get("symbols", []), ensure_ascii=False, separators=(",", ":")),
                "最後嘗試時間(UTC)": record.get("attempted_at"), "成功時間(UTC)": record.get("succeeded_at"),
                "錯誤訊息": record.get("error", ""),
                "嘗試次數": previous_attempts + 1,
            }
            values = [self._serializable(mapped.get(header, ""), header) for header in CLOSE_ALERT_STATE_HEADERS]
            row_number = previous[0] if previous else None
            if row_number:
                updates.append({"range": _sheet_range(CLOSE_ALERT_STATE_SHEET, f"A{row_number}:{end_col}{row_number}"),
                                "values": [values]})
            else:
                appends.append(values)
        if updates:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"valueInputOption": "USER_ENTERED", "data": updates}
            ).execute()
        if appends:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id, range=_sheet_range(CLOSE_ALERT_STATE_SHEET, f"A:{end_col}"),
                valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": appends}
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

    def store_expiration_lookup(
        self,
        *,
        ticker: str,
        request_id: str,
        status: str,
        checked_at: datetime,
        expirations: list[date] | None = None,
        error: str = "",
    ) -> bool:
        """Finish one expiration lookup without overwriting a newer request."""
        self._ensure_sheets([EXPIRATION_CACHE_SHEET], min_columns=len(EXPIRATION_CACHE_HEADERS))
        self._ensure_header(EXPIRATION_CACHE_SHEET, EXPIRATION_CACHE_HEADERS)
        end_col = _column_name(len(EXPIRATION_CACHE_HEADERS))
        response = self._execute(
            self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(EXPIRATION_CACHE_SHEET, f"A2:{end_col}"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
        )
        row_number: int | None = None
        for index, row in enumerate(response.get("values", []), start=2):
            if str(row[0] if row else "").strip().upper() != ticker:
                continue
            existing_request_id = str(row[2] if len(row) > 2 else "").strip()
            if existing_request_id and existing_request_id != request_id:
                return False
            row_number = index
            break

        dates = sorted({value.isoformat() for value in (expirations or [])})
        values = [[
            ticker,
            status,
            request_id,
            checked_at.astimezone(timezone.utc).isoformat(),
            json.dumps(dates, ensure_ascii=False, separators=(",", ":")),
            len(dates),
            error[:1000],
        ]]
        if row_number is None:
            self._execute(
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=_sheet_range(EXPIRATION_CACHE_SHEET, f"A:{end_col}"),
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": values},
                )
            )
        else:
            self._execute(
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=_sheet_range(EXPIRATION_CACHE_SHEET, f"A{row_number}:{end_col}{row_number}"),
                    valueInputOption="RAW",
                    body={"values": values},
                )
            )
        return True

    def _ensure_header(self, sheet_name: str, headers: list[str]) -> None:
        cache_key = (sheet_name, tuple(headers))
        verified = getattr(self, "_verified_headers", set())
        if cache_key in verified:
            return
        end_col = _column_name(len(headers))
        response = self._execute(
            self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(sheet_name, f"A1:{end_col}1"),
                valueRenderOption="UNFORMATTED_VALUE",
            )
        )
        values = response.get("values", [])
        if not values or not any(values[0]):
            self._execute(
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=_sheet_range(sheet_name, f"A1:{end_col}1"),
                    valueInputOption="RAW",
                    body={"values": [headers]},
                )
            )
            verified.add(cache_key)
            self._verified_headers = verified
            return
        existing = [str(value) for value in values[0]]
        if existing != headers:
            raise RuntimeError(f"{sheet_name}欄位與目前版本不一致，請先執行初始化／升級系統")
        verified.add(cache_key)
        self._verified_headers = verified

    def _ensure_sheets(self, titles: list[str], min_columns: int = 26) -> None:
        existing = getattr(self, "_sheet_properties_cache", None)
        if existing is None:
            metadata = self._execute(
                self.service.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id,
                    fields="sheets.properties(sheetId,title,gridProperties(columnCount))",
                )
            )
            existing = {
                sheet["properties"]["title"]: sheet["properties"]
                for sheet in metadata.get("sheets", [])
            }
            self._sheet_properties_cache = existing
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
            self._execute(
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body={"requests": requests}
                )
            )
            self._sheet_properties_cache = None

    def _execute(self, request: Any, max_attempts: int = 5) -> dict[str, Any]:
        """Execute a Sheets request and retry temporary per-minute quota bursts."""
        for attempt in range(max_attempts):
            try:
                return request.execute()
            except Exception as exc:
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status != 429 or attempt >= max_attempts - 1:
                    raise
                sleeper = getattr(self, "_sleep", time.sleep)
                sleeper(min(5 * (2 ** attempt), 30))
        return {}

    def _serializable(self, value: Any, header: str = "") -> Any:
        if value is None:
            return ""
        if isinstance(value, datetime):
            target_timezone = (
                "UTC"
                if "(UTC)" in header
                else _valid_timezone_name(
                    getattr(self, "display_timezone", "Asia/Taipei")
                )
            )
            return _datetime_to_sheet_serial(value, target_timezone)
        if isinstance(value, date):
            return value.isoformat()
        return value
    NOTIFICATION_QUEUE_HEADERS,
    NOTIFICATION_QUEUE_SHEET,
