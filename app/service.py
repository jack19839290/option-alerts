from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .alerts import DISABLED, evaluate_conditions, evaluate_contract_alert, overall_result
from .close_trends import build_close_trend_rows, build_volatility_trend_rows, resolve_market_close
from .greeks import calculate_greeks, time_to_expiry_years
from .market_clock import MarketCalendarError, get_us_option_session_state
from .models import ScanRecord, as_bool
from .pricing import annualized_premium_return, bid_ask_spread_rate, calculate_mid, select_seller_price
from .provider import MarketDataError, RateLimitError, YahooFinanceProvider


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _event_id(prefix: str, *parts: str) -> str:
    raw = "|".join((prefix, *parts))
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _email_item(row: dict[str, Any], *, is_new: bool = False) -> dict[str, Any]:
    return {
        "contract_symbol": row.get("合約代號"), "option_type": row.get("類型"),
        "strike": row.get("履約價"), "underlying_price": row.get("標的股價"),
        "bid": row.get("Bid"), "ask": row.get("Ask"),
        "spread_rate": row.get("Bid-Ask價差率"), "delta": row.get("Delta估算"),
        "annual_return": row.get("年化報酬率"), "open_interest": row.get("未平倉"),
        "dte": row.get("DTE"), "last_fetch": row.get("最後抓取時間").isoformat()
        if isinstance(row.get("最後抓取時間"), datetime) else row.get("最後抓取時間"),
        "is_new": is_new,
    }


class RefreshService:
    def __init__(self, repository: Any, provider: YahooFinanceProvider | None = None):
        self.repository = repository
        self.provider = provider

    def refresh(self, force: bool = False, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        settings = self.repository.load_settings()
        market_timezone = str(settings.get("市場時區") or "America/New_York")
        try:
            session = get_us_option_session_state(now, market_timezone)
        except MarketCalendarError as exc:
            message = f"市場行事曆無法確認：{exc}"
            self.repository.update_settings({"最後執行(UTC)": now.isoformat(), "最後狀態": "市場行事曆失敗"})
            self.repository.append_system_log("ERROR", "市場行事曆失敗", message)
            return {"status": "error", "reason": message}

        automatic_close = session.just_closed and not force
        manual_close_candidate = bool(
            force
            and not session.is_open
            and session.market_close is not None
            and now.astimezone(timezone.utc) > session.market_close.astimezone(timezone.utc)
        )
        close_candidate = automatic_close or manual_close_candidate
        close_time = resolve_market_close(
            now=now,
            market_close=session.market_close,
            market_timezone=market_timezone,
        ) if close_candidate else None
        if not force and not (session.is_open or session.just_closed):
            return self._skip("非期權開盤或收盤更新時點", now, None)

        next_allowed = _parse_utc(settings.get("下次允許抓取(UTC)"))
        if not force and next_allowed and now < next_allowed:
            return self._skip("退避等待中", now, next_allowed)

        headers, scans, invalid_rows = self.repository.load_scans()
        active = [scan for scan in scans if scan.enabled]
        if not active:
            if invalid_rows:
                details = json.dumps(invalid_rows, ensure_ascii=False)
                self.repository.update_settings({"最後執行(UTC)": now.isoformat(), "最後狀態": "掃描設定錯誤"})
                self.repository.append_system_log("ERROR", "掃描設定錯誤", details)
                return {"status": "error", "reason": "沒有可執行的有效掃描", "invalid_rows": invalid_rows}
            disabled = {scan.scan_id: {"狀態": DISABLED, "資料狀態": DISABLED, "工作表": scan.sheet_name} for scan in scans}
            self.repository.update_scan_outputs(headers, scans, disabled)
            return self._skip("沒有啟用的掃描", now, None)

        market_date = close_time.astimezone(ZoneInfo(market_timezone)).date().isoformat() if close_time else ""
        close_existing, previous_closes = self._load_close_history(market_date) if close_candidate else ({}, {})
        close_already_complete = bool(close_candidate) and all(
            close_existing.get(scan.scan_id, {}).get("狀態") == "SUCCESS" for scan in active
        )
        if automatic_close and close_already_complete:
            return self._skip("本交易日收盤更新已完整完成", now, None)
        capture_close = close_candidate and not close_already_complete
        manual_close_recovery = capture_close and manual_close_candidate
        first_close_attempt = capture_close and not close_existing

        previous_states = self.repository.load_chain_states(active)
        updates: dict[str, dict[str, Any]] = {}
        chain_rows: dict[str, list[dict[str, Any]]] = {}
        for scan in scans:
            if not scan.enabled:
                updates[scan.scan_id] = {"狀態": DISABLED, "資料狀態": DISABLED, "工作表": scan.sheet_name}

        provider = self.provider or YahooFinanceProvider(default_dividend_yield=_as_float(settings.get("預設股息殖利率"), 0.0))
        symbol = str(settings.get("無風險利率代號") or "^IRX")
        fallback = _as_float(settings.get("備援無風險利率"), 0.05)
        try:
            risk_free_rate = provider.fetch_risk_free_rate(symbol, fallback)
        except RateLimitError as exc:
            if capture_close and close_time is not None:
                failure_updates = {scan.scan_id: {**self._error_update(scan, now, "Yahoo 流量限制", str(exc)),
                                                  "收盤狀態": "失敗，等待重試"} for scan in active}
                self.repository.update_scan_outputs(headers, scans, failure_updates)
                pending_close = [scan for scan in active if close_existing.get(scan.scan_id, {}).get("狀態") != "SUCCESS"]
                records = [{"record_id": f"{market_date}|{scan.scan_id}", "market_date": market_date,
                            "scan_id": scan.scan_id, "fingerprint": scan.first_condition_fingerprint,
                            "status": "FAILED", "symbols": [], "attempted_at": now, "succeeded_at": None,
                            "error": str(exc)} for scan in pending_close]
                if first_close_attempt and any(scan.first_threshold.enabled and scan.email_enabled for scan in active):
                    self._append_events([{"事件ID": _event_id("CLOSE", market_date, "INITIAL"),
                        "事件類型": "FIRST_CLOSE", "狀態": "PENDING", "建立時間(UTC)": now,
                        "美東交易日": market_date, "是否完整": False,
                        "失敗掃描": [scan.scan_id for scan in pending_close],
                        "內容JSON": {"market_date": market_date,
                                       "capture_mode": "manual_recovery" if manual_close_recovery else "scheduled_close",
                                       "groups": [],
                                       "failed_scans": [scan.scan_id for scan in pending_close], "complete": False}}])
                self._upsert_close_records(records)
                trend_rows = build_close_trend_rows(scans=active, chain_rows={}, scan_updates=failure_updates,
                                                    market_close=close_time, captured_at=now,
                                                    market_timezone=market_timezone, risk_free_rate_source="無法取得")
                self.repository.upsert_close_trend_rows(trend_rows)
            return self._rate_limited(settings, now, str(exc))
        rate_source = str(getattr(provider, "risk_free_rate_source", symbol) or symbol)
        rate_note = str(getattr(provider, "risk_free_rate_note", "") or "")

        groups: dict[tuple[str, object], list[ScanRecord]] = defaultdict(list)
        for scan in active:
            groups[(scan.ticker, scan.expiry)].append(scan)

        success_count = 0
        error_count = len(invalid_rows)
        contract_count = 0
        rate_limit_error = ""
        realtime_events: list[dict[str, Any]] = []
        close_records: list[dict[str, Any]] = []
        close_groups: list[dict[str, Any]] = []

        for (ticker, expiry), group in groups.items():
            try:
                snapshot = provider.fetch_chain(ticker, expiry)
            except RateLimitError as exc:
                rate_limit_error = str(exc)
                error_count += len(group)
                for scan in group:
                    updates[scan.scan_id] = self._error_update(scan, now, "Yahoo 流量限制", str(exc))
                break
            except MarketDataError as exc:
                error_count += len(group)
                for scan in group:
                    updates[scan.scan_id] = self._error_update(scan, now, "抓取失敗", str(exc))
                continue

            for scan in group:
                state_matches = str(scan.values.get("第二條件指紋") or "") == scan.second_condition_fingerprint
                scan_states = previous_states.get(scan.scan_id, {}) if state_matches else {}
                rows: list[dict[str, Any]] = []
                new_realtime: list[dict[str, Any]] = []
                all_realtime_matches: list[dict[str, Any]] = []
                first_count = second_count = 0
                quotes = [q for q in snapshot.quotes if scan.display_type == "ALL" or q.option_type == scan.display_type]
                for quote in quotes:
                    _, dte = time_to_expiry_years(scan.expiry, now=now, market_timezone=market_timezone)
                    mid = calculate_mid(quote.bid, quote.ask)
                    spread = bid_ask_spread_rate(quote.bid, quote.ask)
                    seller_price, seller_source = select_seller_price(quote.bid)
                    greeks = None
                    if snapshot.underlying_price is not None and quote.implied_volatility is not None and quote.implied_volatility > 0:
                        greeks = calculate_greeks(option_type=quote.option_type, spot=snapshot.underlying_price,
                                                  strike=quote.strike, volatility=quote.implied_volatility,
                                                  risk_free_rate=risk_free_rate, dividend_yield=snapshot.dividend_yield,
                                                  expiry=scan.expiry, now=now, market_timezone=market_timezone)
                    capital = quote.strike if quote.option_type == "PUT" else scan.call_cost_basis
                    annual = annualized_premium_return(seller_premium=seller_price, capital_basis=capital, dte=dte)
                    delta = greeks.delta if greeks else None
                    first = evaluate_conditions(conditions=scan.first_threshold, delta=delta, spread_rate=spread,
                                                annual_return=annual, open_interest=quote.open_interest)
                    second = evaluate_conditions(conditions=scan.second_threshold, delta=delta, spread_rate=spread,
                                                 annual_return=annual, open_interest=quote.open_interest)
                    first_count += int(first.matched is True)
                    second_count += int(second.matched is True)
                    previous = scan_states.get(quote.contract_symbol, {})
                    armed_raw = previous.get("第二可再次通知")
                    alert = evaluate_contract_alert(
                        evaluation=second,
                        previous_armed=as_bool(armed_raw) if armed_raw not in (None, "") else None,
                        previous_nonmatches=_as_int(previous.get("第二連續有效不符合")),
                        previous_sequence=_as_int(previous.get("第二通知序號"), 1),
                        email_enabled=scan.email_enabled,
                    )
                    first_result, second_result = overall_result(first), overall_result(second)
                    if first.matched is True and second.matched is True:
                        matched_label, priority = "第一＋第二", 0
                    elif second.matched is True:
                        matched_label, priority = "第二門檻", 1
                    elif first.matched is True:
                        matched_label, priority = "第一門檻", 2
                    elif first.matched is None or second.matched is None:
                        matched_label, priority = "資料不足", 4
                    else:
                        matched_label, priority = "未符合", 3
                    issues = [item for item in (rate_note, snapshot.dividend_yield_note,
                              "標的股價不足" if snapshot.underlying_price is None else "",
                              "Bid無效" if seller_price is None else "",
                              "Bid-Ask價差資料不足" if spread is None else "",
                              "Greeks資料不足" if greeks is None else "",
                              "未平倉資料不足" if quote.open_interest is None else "") if item]
                    needs_call_cost = quote.option_type == "CALL" and scan.call_cost_basis is None and (
                        scan.first_threshold.annual_return_threshold is not None or scan.second_threshold.annual_return_threshold is not None)
                    if needs_call_cost:
                        issues.append("CALL未填持股成本")
                    row = {
                        "符合門檻": matched_label, "第一門檻結果": first_result, "第二門檻結果": second_result,
                        "類型": quote.option_type, "履約價": quote.strike, "標的股價": snapshot.underlying_price,
                        "Bid": quote.bid, "年化報酬率": annual,
                        "第一年化報酬率結果": first.annual_return_result, "第二年化報酬率結果": second.annual_return_result,
                        "Delta估算": delta, "第一Delta結果": first.delta_result, "第二Delta結果": second.delta_result,
                        "Bid-Ask價差率": spread, "第一Bid-Ask價差結果": first.spread_result,
                        "第二Bid-Ask價差結果": second.spread_result, "未平倉": quote.open_interest,
                        "第一未平倉結果": first.open_interest_result, "第二未平倉結果": second.open_interest_result,
                        "DTE": dte, "最後抓取時間": now, "Ask": quote.ask, "Mid": mid, "Last": quote.last_price,
                        "成交量": quote.volume,
                        "標的－履約價差": snapshot.underlying_price - quote.strike if snapshot.underlying_price is not None else None,
                        "最後成交時間": quote.last_trade_time, "Gamma估算": greeks.gamma if greeks else None,
                        "Theta估算(每日)": greeks.theta_per_day if greeks else None,
                        "Vega估算(每1%)": greeks.vega_per_pct if greeks else None,
                        "IV": quote.implied_volatility, "年化本金": capital, "賣出試算價": seller_price,
                        "試算價來源": seller_source, "無風險利率": risk_free_rate,
                        "股息殖利率": snapshot.dividend_yield, "Greeks模型": "Black-Scholes-Merton (估算)",
                        "|Delta|": abs(delta) if delta is not None else None, "合約代號": quote.contract_symbol,
                        "掃描ID": scan.scan_id, "第二通知狀態": alert.status, "第二可再次通知": alert.armed,
                        "第二連續有效不符合": alert.consecutive_nonmatches, "第二通知序號": alert.sequence,
                        "資料狀態": "；".join(issues) if issues else "正常", "_priority": priority,
                    }
                    rows.append(row)
                    if second.matched is True:
                        item = _email_item(row)
                        item["sequence"] = alert.sequence
                        item["triggered_now"] = bool(alert.pending_email)
                        all_realtime_matches.append(item)
                        if alert.pending_email:
                            new_realtime.append(dict(item))

                rows.sort(key=lambda row: (row["_priority"], row["類型"], row["履約價"]))
                for row in rows:
                    row.pop("_priority", None)
                chain_rows[scan.scan_id] = rows
                if new_realtime:
                    signature = ",".join(sorted(f"{x['contract_symbol']}:{x['sequence']}" for x in new_realtime))
                    realtime_events.append({
                        "事件ID": _event_id("RT", scan.scan_id, scan.second_condition_fingerprint, signature),
                        "事件類型": "SECOND_REALTIME", "狀態": "PENDING", "建立時間(UTC)": now,
                        "掃描ID": scan.scan_id, "股票代號": scan.ticker, "到期日": scan.expiry,
                        "是否完整": True, "內容JSON": {"complete": True, "snapshot_version": 2,
                            "groups": [{"scan_id": scan.scan_id, "ticker": scan.ticker,
                            "expiry": scan.expiry.isoformat(), "items": new_realtime,
                            "all_matching_items": all_realtime_matches}]},
                    })
                scan_status = "正常" if rows and all(r["資料狀態"] == "正常" for r in rows) else "部分資料不足" if rows else "期權鍊無資料"
                updates[scan.scan_id] = {
                    "狀態": "掃描中", "標的股價": snapshot.underlying_price, "合約數": len(rows),
                    "第一符合數": first_count, "第二符合數": second_count, "最後嘗試時間": now,
                    "最後成功抓取時間": now, "資料狀態": scan_status, "錯誤訊息": "",
                    "工作表": scan.sheet_name, "第一條件指紋": scan.first_condition_fingerprint,
                    "第二條件指紋": scan.second_condition_fingerprint,
                }
                if capture_close:
                    updates[scan.scan_id]["收盤狀態"] = "成功"
                    updates[scan.scan_id]["收盤最後成功交易日"] = market_date
                success_count += 1
                contract_count += len(rows)

                if capture_close:
                    if close_existing.get(scan.scan_id, {}).get("狀態") != "SUCCESS":
                        previous_close = previous_closes.get(scan.scan_id)
                        previous_symbols = set(previous_close.get("symbols", [])) if previous_close else set()
                        same_fingerprint = bool(previous_close and previous_close.get("fingerprint") == scan.first_condition_fingerprint)
                        matches = [row for row in rows if row["第一門檻結果"] == "符合"]
                        items = [_email_item(row, is_new=same_fingerprint and str(row["合約代號"]) not in previous_symbols) for row in matches]
                        baseline_changed = bool(previous_close and not same_fingerprint)
                        close_records.append({"record_id": f"{market_date}|{scan.scan_id}", "market_date": market_date,
                                              "scan_id": scan.scan_id, "fingerprint": scan.first_condition_fingerprint,
                                              "status": "SUCCESS", "symbols": [row["合約代號"] for row in matches],
                                              "attempted_at": now, "succeeded_at": now, "error": ""})
                        if scan.first_threshold.enabled and scan.email_enabled:
                            close_groups.append({"scan_id": scan.scan_id, "ticker": scan.ticker,
                                                 "expiry": scan.expiry.isoformat(), "items": items,
                                                 "all_matching_items": items,
                                                 "baseline_changed": baseline_changed})

        if rate_limit_error:
            for scan in active:
                if scan.scan_id not in chain_rows and scan.scan_id not in updates:
                    updates[scan.scan_id] = self._error_update(scan, now, "Yahoo 流量限制", rate_limit_error)
        failed_scans = [scan for scan in active if scan.scan_id not in chain_rows]
        error_count = max(error_count, len(invalid_rows) + len(failed_scans))
        if capture_close:
            close_failures = [scan for scan in failed_scans if close_existing.get(scan.scan_id, {}).get("狀態") != "SUCCESS"]
            for scan in close_failures:
                update = updates.get(scan.scan_id, {})
                update["收盤狀態"] = "失敗，等待重試"
                close_records.append({"record_id": f"{market_date}|{scan.scan_id}", "market_date": market_date,
                                      "scan_id": scan.scan_id, "fingerprint": scan.first_condition_fingerprint,
                                      "status": "FAILED", "symbols": [], "attempted_at": now, "succeeded_at": None,
                                      "error": str(update.get("錯誤訊息") or update.get("資料狀態") or "未完成")})
            succeeded_now = {record["scan_id"] for record in close_records if record["status"] == "SUCCESS"}
            if first_close_attempt:
                selected_groups = close_groups
                event_type = "FIRST_CLOSE"
                suffix = "INITIAL"
            else:
                newly_succeeded = {scan_id for scan_id in succeeded_now if close_existing.get(scan_id, {}).get("狀態") != "SUCCESS"}
                selected_groups = [group for group in close_groups if group["scan_id"] in newly_succeeded]
                event_type = "FIRST_CLOSE_SUPPLEMENT"
                suffix = ",".join(sorted(newly_succeeded))
            eligible_first = any(scan.first_threshold.enabled and scan.email_enabled for scan in active)
            if eligible_first and (first_close_attempt or selected_groups):
                realtime_events.append({
                    "事件ID": _event_id("CLOSE", market_date, suffix), "事件類型": event_type,
                    "狀態": "PENDING", "建立時間(UTC)": now, "美東交易日": market_date,
                    "是否完整": not close_failures, "失敗掃描": [scan.scan_id for scan in close_failures],
                    "內容JSON": {"market_date": market_date, "snapshot_version": 2,
                                   "capture_mode": "manual_recovery" if manual_close_recovery else "scheduled_close",
                                   "groups": selected_groups,
                                   "failed_scans": [scan.scan_id for scan in close_failures],
                                   "complete": not close_failures},
                })

        self.repository.update_scan_outputs(headers, scans, updates)
        self._append_events(realtime_events)
        self.repository.write_chain_sheets(scans, chain_rows)

        close_trend_count = 0
        if capture_close and close_time is not None:
            trend_rows = build_close_trend_rows(scans=active, chain_rows=chain_rows, scan_updates=updates,
                                                market_close=close_time, captured_at=now,
                                                market_timezone=market_timezone, risk_free_rate_source=rate_source)
            self.repository.upsert_close_trend_rows(trend_rows)
            volatility_rows = build_volatility_trend_rows(scans=active, chain_rows=chain_rows,
                scan_updates=updates, market_close=close_time, captured_at=now, market_timezone=market_timezone)
            self.repository.upsert_volatility_trend_rows(volatility_rows)
            close_trend_count = len(trend_rows)
        if capture_close:
            # Mark completion only after both historical worksheets are saved.
            self._upsert_close_records(close_records)

        if rate_limit_error:
            return self._rate_limited(settings, now, rate_limit_error, already_written=True)

        complete = success_count == len(active) and not invalid_rows
        status = "成功" if complete else "部分成功"
        settings_update = {"連續失敗次數": 0 if complete else _as_int(settings.get("連續失敗次數")),
                           "下次允許抓取(UTC)": "" if complete else settings.get("下次允許抓取(UTC)", ""),
                           "最後執行(UTC)": now.isoformat(), "最後狀態": status,
                           "GitHub 最後要求狀態": (
                               "工作流程完成：資料更新成功" if complete
                               else "工作流程完成：部分資料失敗，請查看系統紀錄"
                           )}
        if complete:
            settings_update["最後成功抓取(UTC)"] = now.isoformat()
        self.repository.update_settings(settings_update)
        details = {"scans": success_count, "active_scans": len(active), "contracts": contract_count,
                   "errors": error_count, "invalid_rows": invalid_rows, "market_open": session.is_open,
                   "close_update": capture_close,
                   "close_recovery": manual_close_recovery,
                   "close_complete": capture_close and not (close_failures if capture_close else []),
                   "close_trend_rows": close_trend_count, "queued_events": len(realtime_events),
                   "risk_free_rate": risk_free_rate, "risk_free_rate_source": rate_source}
        self.repository.append_system_log("INFO" if complete else "WARN", status, json.dumps(details, ensure_ascii=False))
        return {"status": status, **details}

    def _load_close_history(self, market_date: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        if hasattr(self.repository, "load_close_history"):
            return self.repository.load_close_history(market_date)
        current = self.repository.load_close_records(market_date) if hasattr(self.repository, "load_close_records") else {}
        return current, {}

    def _upsert_close_records(self, records: list[dict[str, Any]]) -> None:
        if hasattr(self.repository, "upsert_close_records"):
            self.repository.upsert_close_records(records)

    def _append_events(self, events: list[dict[str, Any]]) -> None:
        if events and hasattr(self.repository, "append_notification_events"):
            self.repository.append_notification_events(events)

    def _error_update(self, scan: ScanRecord, now: datetime, status: str, message: str) -> dict[str, Any]:
        return {"狀態": "錯誤", "最後嘗試時間": now, "資料狀態": status,
                "錯誤訊息": message[:1000], "工作表": scan.sheet_name}

    def _rate_limited(self, settings: dict[str, Any], now: datetime, message: str,
                      already_written: bool = False) -> dict[str, Any]:
        failures = _as_int(settings.get("連續失敗次數")) + 1
        next_allowed = now + timedelta(minutes=min(15 * (2 ** (failures - 1)), 60))
        self.repository.update_settings({"連續失敗次數": failures, "下次允許抓取(UTC)": next_allowed.isoformat(),
                                         "最後執行(UTC)": now.isoformat(), "最後狀態": "Yahoo 流量限制"})
        self.repository.append_system_log("WARN", "Yahoo 流量限制", message)
        return {"status": "rate_limited", "next_allowed": next_allowed.isoformat(), "already_written": already_written}

    def _skip(self, reason: str, now: datetime, next_run: datetime | None) -> dict[str, Any]:
        self.repository.update_settings({"最後執行(UTC)": now.isoformat(), "最後狀態": reason})
        result: dict[str, Any] = {"status": "skipped", "reason": reason}
        if next_run is not None:
            result["next_run"] = next_run.isoformat()
        return result
