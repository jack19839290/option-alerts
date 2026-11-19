import argparse
import os
from datetime import datetime, timedelta, timezone
from decimal import InvalidOperation

from app.market_clock import get_us_option_session_state
from app.provider import MarketDataError, RateLimitError, YahooFinanceProvider

from .screen import MARKET_ZONE, evaluate
from .sheet import LongCallSheet


def email_summary(results):
    lines = [
        f"{ticker}   {expiry}   DTE {dte}   履約價 ${strike:.2f}   "
        f"Delta {delta:.3f}   OI {oi}   Spread {spread:.2%}   "
        f"釋放 {cash:.2%}   年化 {cost:.2%}   最高買價 {ceiling or '—'}   "
        f"{source} ${price:.3f}   Ask ${ask:.2f}"
        for ticker, expiry, dte, strike, delta, oi, spread, cash, cost, ceiling,
        source, price, _, _, _, ask, *_ in results[:40]
    ]
    if len(results) > 40:
        lines.append("其餘合約請見試算表「符合條件」。")
    return "\n".join(lines)


def scan(sheet, close=False, now=None, provider=None, run_id=""):
    clock = now or datetime.now(timezone.utc)
    market_day = clock.astimezone(MARKET_ZONE).date()
    if close:
        state = get_us_option_session_state(clock)
        if state.market_close is None or clock < state.market_close + timedelta(minutes=5):
            print("未到此交易日的收盤更新時段")
            return 0
    log = sheet.read("log", "A:L")
    if any(len(row) >= 12 and row[11] == run_id for row in log[1:]) and run_id:
        print("本次執行已寫入")
        return 0
    if close and any(len(row) >= 3 and row[1:3] == [market_day.isoformat(), "收盤"] for row in log[1:]):
        print("本交易日已有收盤結果")
        return 0

    issues = []
    try:
        targets, issues = sheet.load_targets()
    except (ValueError, InvalidOperation) as exc:
        targets = {}
        issues = [f"全表預設值無效：{exc}"]
    provider = provider or YahooFinanceProvider()
    rows, results, info = [], [], []
    expected = received = 0
    rate = 0.04
    if targets:
        try:
            rate = provider.fetch_risk_free_rate("^IRX", rate)
            if provider.risk_free_rate_note:
                info.append(provider.risk_free_rate_note)
        except RateLimitError:
            info.append("利率來源限流，Delta 採備援利率 4%")
    limited = False
    for ticker, thresholds in targets.items():
        if limited:
            issues.append(f"{ticker}：Yahoo 限流，尚未查詢")
            continue
        try:
            dates = provider.fetch_expirations(ticker)
        except RateLimitError:
            issues.append(f"{ticker}：Yahoo 限流，無法取得到期日")
            limited = True
            continue
        except MarketDataError as exc:
            issues.append(str(exc))
            continue
        dates = [
            expiry for expiry in dates
            if thresholds.min_dte <= (expiry - market_day).days <= thresholds.max_dte
        ]
        expected += len(dates)
        if not dates:
            info.append(f"{ticker}：天期範圍內無掛牌到期日")
        for expiry in dates:
            if limited:
                issues.append(f"{ticker} {expiry}：Yahoo 限流，尚未掃描")
                continue
            try:
                chain = provider.fetch_chain(ticker, expiry, calls_only=True)
            except RateLimitError:
                issues.append(f"{ticker} {expiry}：Yahoo 限流")
                limited = True
                continue
            except MarketDataError as exc:
                issues.append(str(exc))
                continue
            calls = [quote for quote in chain.quotes if quote.option_type == "CALL"]
            if not calls or chain.underlying_price is None:
                issues.append(f"{ticker} {expiry}：缺少 Call 或標的股價")
                continue
            received += 1
            fetched = datetime.now(timezone.utc)
            for quote in calls:
                result = evaluate(chain, quote, thresholds, clock, fetched, rate)
                rows.append(result.row)
                if result.passed:
                    results.append(result.row)

    results.sort(key=lambda row: (row[0], row[8], row[1], row[3]))
    rows.sort(key=lambda row: (row[0], row[1], row[3]))
    if issues:
        status = "部分完成" if received else "失敗"
    else:
        status = "完成" if targets else "尚未啟用標的"
    notes = "\n".join(issues + info)[:8000]
    sheet.publish(results, rows, [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        market_day.isoformat(), "收盤" if close else "手動", status, len(targets),
        expected, received, len(results), notes,
        "待寄" if close and (targets or issues) else "",
        email_summary(results) if close else "", run_id,
    ], len(log))
    print(f"{status}，已掃 {received}/{expected} 個到期日，符合 {len(results)} 筆")
    return int(bool(issues))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--close", action="store_true")
    args = parser.parse_args()
    sheet_id = os.environ.get("LONG_CALL_SPREADSHEET_ID")
    if not sheet_id or sheet_id == os.environ.get("PUT_SPREADSHEET_ID"):
        parser.error("LONG_CALL_SPREADSHEET_ID 必須設定為獨立的買入買權試算表")
    return scan(LongCallSheet(sheet_id), close=args.close, run_id=os.getenv("GITHUB_RUN_ID", ""))


if __name__ == "__main__":
    raise SystemExit(main())
