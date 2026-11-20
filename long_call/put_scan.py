import argparse
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import InvalidOperation

from app.market_clock import get_us_option_session_state
from app.models import as_bool
from app.provider import MarketDataError, RateLimitError, YahooFinanceProvider

from .put import DEFAULTS, HEADERS, PASSED, PENDING, SCHEMA, SETTINGS, evaluate, thresholds
from .screen import MARKET_ZONE
from .sheet import LongCallSheet, row_data


class PutSheet(LongCallSheet):
    schema = SCHEMA
    headers = HEADERS
    formats = tuple((i, i + 1, "PERCENT", "0.00%") for i in (
        4, 6, 7, 8, 17, 20, 29, 30, 35, 36, 40, 41, 45, 46, 50, 51,
    ))

    def get_tabs(self):
        tabs = super().get_tabs()
        specs = {
            "settings": (len(SETTINGS), 9, [
                ["買入賣權避險設定"], ["個別標的留白沿用預設。開關可在網頁設定。"],
                [], [], ["全表預設", "", *DEFAULTS], [], [], [], SETTINGS,
            ]),
            "results": (len(HEADERS), 1, [HEADERS]),
            "detail": (len(HEADERS), 1, [HEADERS]),
            "log": (len(SCHEMA["logs"]), 1, [SCHEMA["logs"]]),
        }
        used = {tab["properties"]["sheetId"] for tab in tabs.values()}
        requests = []
        for key, (width, frozen, rows) in specs.items():
            if SCHEMA[key] in tabs:
                continue
            sheet_id = next(i for i in range(100, 10000) if i not in used)
            used.add(sheet_id)
            requests.extend([
                {"addSheet": {"properties": {"sheetId": sheet_id, "title": SCHEMA[key],
                    "gridProperties": {"rowCount": 200, "columnCount": width, "frozenRowCount": frozen}}}},
                {"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                    "rows": [row_data(row) for row in rows], "fields": "userEnteredValue"}},
                {"repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": frozen - 1, "endRowIndex": frozen},
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": .12, "green": .25, "blue": .69},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
                    "fields": "userEnteredFormat",
                }},
            ])
            if key == "settings":
                for column, header in enumerate(SETTINGS[2:], 2):
                    if any(word in header for word in ("Spread", "保費率", "年化成本", "跌幅")) and not header.startswith("啟用"):
                        requests.append({"repeatCell": {
                            "range": {"sheetId": sheet_id, "startColumnIndex": column, "endColumnIndex": column + 1},
                            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}},
                            "fields": "userEnteredFormat.numberFormat",
                        }})
        if not requests:
            return tabs
        self.api.batchUpdate(spreadsheetId=self.id, body={"requests": requests}).execute(num_retries=0)
        return super().get_tabs()

    def load_targets(self):
        rows = self.read("settings", "A5:R")
        if len(rows) < 5 or rows[4] != SETTINGS:
            raise ValueError("Put 設定欄位不符")
        defaults = rows[0][2:]
        thresholds(defaults)
        targets, issues = {}, []
        for number, row in enumerate(rows[5:], 10):
            if not row or not as_bool(row[0]):
                continue
            try:
                row = (row + [""] * len(SETTINGS))[:len(SETTINGS)]
                ticker = str(row[1]).strip().upper()
                if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,11}", ticker):
                    raise ValueError("股票代號無效")
                if ticker in targets:
                    raise ValueError(f"{ticker} 重複啟用")
                targets[ticker] = thresholds([
                    default if value == "" else value for value, default in zip(row[2:], defaults, strict=True)
                ])
            except (ValueError, InvalidOperation) as exc:
                issues.append(f"第 {number} 列｜{exc}")
        return targets, issues


def scan(sheet, close=False, now=None, provider=None, run_id=""):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(MARKET_ZONE).date()
    if close:
        state = get_us_option_session_state(now)
        if state.market_close is None or now < state.market_close + timedelta(minutes=5):
            print("未到此交易日的收盤更新時段")
            return 0
    logs = sheet.read("log", "A:K")
    if any(run_id and len(row) >= 11 and row[10] == run_id and row[3] == "完成" for row in logs[1:]):
        return 0
    if close and any(row[1:4] == [day.isoformat(), "收盤", "完成"] for row in logs[1:]):
        return 0

    provider = provider or YahooFinanceProvider()
    try:
        targets, issues = sheet.load_targets()
    except (ValueError, InvalidOperation) as exc:
        targets, issues = {}, [f"全表預設值無效｜{exc}"]
    details, notes = [], []
    expected = received = 0
    limited = False
    rate = 0.04
    if targets:
        try:
            rate = provider.fetch_risk_free_rate("^IRX", rate)
            if provider.risk_free_rate_note:
                notes.append(provider.risk_free_rate_note)
        except RateLimitError:
            notes.append("利率來源限流，模型採備援利率 4%")
    for ticker, limits in sorted(targets.items()):
        if limited:
            issues.append(f"{ticker}｜Yahoo 限流，尚未查詢到期日")
            continue
        try:
            dates = provider.fetch_expirations(ticker)
        except MarketDataError as exc:
            issues.append(f"{ticker}｜{exc}")
            limited = isinstance(exc, RateLimitError)
            continue
        bounds = limits["DTE"]
        eligible = [expiry for expiry in dates if expiry >= day
                    and (bounds is None or bounds[0] <= (expiry - day).days <= bounds[1])]
        expected += len(eligible)
        if bounds and len(eligible) < len(dates):
            notes.append(f"{ticker}｜依 DTE 預篩略過 {len(dates) - len(eligible)} 個到期日")
        for expiry in eligible:
            if limited:
                issues.append(f"{ticker} {expiry}｜Yahoo 限流，尚未查詢")
                continue
            try:
                chain = provider.fetch_chain(ticker, expiry)
            except MarketDataError as exc:
                issues.append(f"{ticker} {expiry}｜{exc}")
                limited = isinstance(exc, RateLimitError)
                continue
            puts = [quote for quote in chain.quotes if quote.option_type == "PUT"]
            if not puts or chain.underlying_price is None:
                issues.append(f"{ticker} {expiry}｜缺少 Put 或股價")
                continue
            received += 1
            fetched = datetime.now(timezone.utc)
            details.extend(evaluate(chain, quote, limits, now, fetched, rate) for quote in puts)
    status = ("部分完成" if received else "失敗") if issues else ("完成" if targets else "尚未啟用標的")
    results = [row for row in details if row[22] == PASSED]
    pending = sum(row[22] == PENDING for row in details)
    sheet.publish(results if status != "失敗" else None, details if status != "失敗" else None, [
        datetime.now(timezone.utc).isoformat(timespec="seconds"), day.isoformat(),
        "收盤" if close else "手動", status, len(targets), expected, received, len(results),
        pending, "；".join(issues + notes)[:8000], run_id,
    ], max(1, len(logs)))
    print(f"Put {status}｜已取得 {received}/{expected} 個到期日，符合 {len(results)}，待確認 {pending}")
    return int(bool(issues))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--close", action="store_true")
    args = parser.parse_args()
    sheet_id = os.environ.get("LONG_CALL_SPREADSHEET_ID")
    if not sheet_id or sheet_id == os.environ.get("PUT_SPREADSHEET_ID"):
        parser.error("LONG_CALL_SPREADSHEET_ID 必須設定為獨立的買入買權試算表")
    return scan(PutSheet(sheet_id), close=args.close, run_id=os.getenv("GITHUB_RUN_ID", ""))


if __name__ == "__main__":
    raise SystemExit(main())
