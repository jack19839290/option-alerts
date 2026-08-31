from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .alerts import DISABLED, evaluate_conditions, evaluate_contract_alert
from .close_trends import build_close_trend_rows, resolve_market_close
from .greeks import calculate_greeks, time_to_expiry_years
from .market_clock import get_us_option_session_state
from .models import ScanRecord, as_bool
from .pricing import (
    annualized_premium_return,
    bid_ask_spread_rate,
    calculate_mid,
    select_seller_price,
)
from .provider import MarketDataError, RateLimitError, YahooFinanceProvider


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_int(value: Any, fallback: int) -> int:
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


def _existing_pending(value: Any) -> dict[str, Any]:
    if not value:
        return {"total": 0, "items": []}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"total": 0, "items": []}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        return {"total": 0, "items": []}
    return parsed


def _merge_pending(
    existing_value: Any, new_items: list[dict[str, Any]], generated_at: datetime
) -> str:
    existing = _existing_pending(existing_value)
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*existing.get("items", []), *new_items]:
        symbol = str(item.get("contract_symbol") or "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        combined.append(item)
    if not combined:
        return ""
    previous_total = _as_int(existing.get("total"), len(existing.get("items", [])))
    newly_added = sum(
        1
        for item in new_items
        if str(item.get("contract_symbol") or "")
        not in {
            str(old.get("contract_symbol") or "")
            for old in existing.get("items", [])
        }
    )
    payload = {
        "generated_at": generated_at.isoformat(),
        "total": max(len(combined), previous_total + newly_added),
        "items": combined[:20],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
        session = get_us_option_session_state(now, market_timezone)
        is_open = session.is_open
        capture_close_trend = session.just_closed and not force
        close_time = (
            resolve_market_close(
                now=now,
                market_close=session.market_close,
                market_timezone=market_timezone,
            )
            if capture_close_trend
            else None
        )

        if not force and not (session.is_open or session.just_closed):
            return self._skip("非期權開盤或收盤更新時點", now, None)

        last_success = _parse_utc(settings.get("最後成功抓取(UTC)"))
        if (
            not force
            and session.just_closed
            and session.market_close is not None
            and last_success is not None
            and last_success >= session.market_close
        ):
            return self._skip("本交易日收盤更新已完成", now, None)

        next_allowed = _parse_utc(settings.get("下次允許抓取(UTC)"))
        if not force and next_allowed and now < next_allowed:
            return self._skip("退避等待中", now, next_allowed)

        headers, scans, invalid_rows = self.repository.load_scans()
        active = [scan for scan in scans if scan.enabled]
        previous_states = self.repository.load_chain_states(active)
        updates: dict[str, dict[str, Any]] = {}
        chain_rows: dict[str, list[dict[str, Any]]] = {}
        for scan in scans:
            if not scan.enabled:
                updates[scan.scan_id] = {
                    "狀態": DISABLED,
                    "資料狀態": DISABLED,
                    "待寄信": "",
                    "工作表": scan.sheet_name,
                }

        provider = self.provider or YahooFinanceProvider(
            default_dividend_yield=_as_float(settings.get("預設股息殖利率"), 0.0)
        )
        risk_free_symbol = str(settings.get("無風險利率代號") or "^IRX")
        fallback_risk_free = _as_float(settings.get("備援無風險利率"), 0.05)
        try:
            risk_free_rate = provider.fetch_risk_free_rate(
                risk_free_symbol, fallback_risk_free
            )
        except RateLimitError as exc:
            if capture_close_trend and close_time is not None:
                failure_updates = {
                    scan.scan_id: self._error_update(
                        scan, now, "Yahoo 流量限制", str(exc)
                    )
                    for scan in active
                }
                trend_rows = build_close_trend_rows(
                    scans=active,
                    chain_rows={},
                    scan_updates=failure_updates,
                    market_close=close_time,
                    captured_at=now,
                    market_timezone=market_timezone,
                    risk_free_rate_source="無法取得",
                )
                self.repository.upsert_close_trend_rows(trend_rows)
            return self._rate_limited(settings, now, str(exc))
        risk_free_rate_source = str(
            getattr(provider, "risk_free_rate_source", risk_free_symbol)
            or risk_free_symbol
        )
        risk_free_rate_note = str(
            getattr(provider, "risk_free_rate_note", "") or ""
        )

        groups: dict[tuple[str, object], list[ScanRecord]] = defaultdict(list)
        for scan in active:
            groups[(scan.ticker, scan.expiry)].append(scan)

        success_count = 0
        contract_count = 0
        error_count = len(invalid_rows)
        rate_limit_error = ""
        for (ticker, expiry), group in groups.items():
            try:
                snapshot = provider.fetch_chain(ticker, expiry)
            except RateLimitError as exc:
                rate_limit_error = str(exc)
                error_count += len(group)
                for scan in group:
                    updates[scan.scan_id] = self._error_update(
                        scan, now, "Yahoo 流量限制", str(exc)
                    )
                break
            except MarketDataError as exc:
                error_count += len(group)
                for scan in group:
                    updates[scan.scan_id] = self._error_update(
                        scan, now, "抓取失敗", str(exc)
                    )
                continue

            for scan in group:
                fingerprint_matches = (
                    str(scan.values.get("條件指紋") or "")
                    == scan.condition_fingerprint
                )
                baseline_established = scan.baseline_established and fingerprint_matches
                scan_states = previous_states.get(scan.scan_id, {})
                rows: list[dict[str, Any]] = []
                new_alerts: list[dict[str, Any]] = []
                matching_count = 0
                quotes = [
                    quote
                    for quote in snapshot.quotes
                    if scan.display_type == "ALL" or quote.option_type == scan.display_type
                ]
                quotes.sort(key=lambda quote: (quote.strike, quote.option_type))
                for quote in quotes:
                    _, dte = time_to_expiry_years(
                        scan.expiry, now=now, market_timezone=market_timezone
                    )
                    midpoint = calculate_mid(quote.bid, quote.ask)
                    spread_rate = bid_ask_spread_rate(quote.bid, quote.ask)
                    seller_price, seller_source = select_seller_price(quote.bid)
                    greeks = None
                    if (
                        snapshot.underlying_price is not None
                        and quote.implied_volatility is not None
                        and quote.implied_volatility > 0
                    ):
                        greeks = calculate_greeks(
                            option_type=quote.option_type,
                            spot=snapshot.underlying_price,
                            strike=quote.strike,
                            volatility=quote.implied_volatility,
                            risk_free_rate=risk_free_rate,
                            dividend_yield=snapshot.dividend_yield,
                            expiry=scan.expiry,
                            now=now,
                            market_timezone=market_timezone,
                        )
                    capital_basis = (
                        quote.strike if quote.option_type == "PUT" else scan.call_cost_basis
                    )
                    annual_return = annualized_premium_return(
                        seller_premium=seller_price,
                        capital_basis=capital_basis,
                        dte=dte,
                    )
                    evaluation = evaluate_conditions(
                        scan=scan,
                        delta=greeks.delta if greeks else None,
                        spread_rate=spread_rate,
                        annual_return=annual_return,
                        open_interest=quote.open_interest,
                    )
                    if evaluation.matched is True:
                        matching_count += 1

                    previous = scan_states.get(quote.contract_symbol, {})
                    armed_value = previous.get("可再次通知")
                    previous_armed = (
                        as_bool(armed_value) if armed_value not in (None, "") else None
                    )
                    alert = evaluate_contract_alert(
                        evaluation=evaluation,
                        baseline_established=baseline_established,
                        previous_armed=previous_armed,
                        previous_nonmatches=_as_int(
                            previous.get("連續有效不符合"), 0
                        ),
                        email_enabled=scan.email_enabled,
                    )
                    if not evaluation.has_active_conditions:
                        overall_result = "尚未設定條件"
                    elif evaluation.matched is None:
                        overall_result = "資料不足"
                    else:
                        overall_result = "符合" if evaluation.matched else "未符合"

                    data_issues: list[str] = []
                    if risk_free_rate_note:
                        data_issues.append(risk_free_rate_note)
                    if snapshot.dividend_yield_note:
                        data_issues.append(snapshot.dividend_yield_note)
                    if snapshot.underlying_price is None:
                        data_issues.append("標的股價不足")
                    if seller_price is None:
                        data_issues.append("Bid無效")
                    if spread_rate is None:
                        data_issues.append("Bid-Ask價差資料不足")
                    if greeks is None:
                        data_issues.append("Greeks資料不足")
                    if quote.open_interest is None:
                        data_issues.append("未平倉資料不足")
                    if (
                        quote.option_type == "CALL"
                        and scan.call_cost_basis is None
                        and scan.annual_return_threshold is not None
                    ):
                        data_issues.append("CALL未填持股成本")

                    row = {
                        "掃描ID": scan.scan_id,
                        "類型": quote.option_type,
                        "履約價": quote.strike,
                        "合約代號": quote.contract_symbol,
                        "標的股價": snapshot.underlying_price,
                        "Last": quote.last_price,
                        "Bid": quote.bid,
                        "Ask": quote.ask,
                        "Mid": midpoint,
                        "Bid-Ask價差率": spread_rate,
                        "賣出試算價": seller_price,
                        "試算價來源": seller_source,
                        "IV": quote.implied_volatility,
                        "無風險利率": risk_free_rate,
                        "股息殖利率": snapshot.dividend_yield,
                        "Greeks模型": "Black-Scholes-Merton (估算)",
                        "Delta估算": greeks.delta if greeks else None,
                        "Gamma估算": greeks.gamma if greeks else None,
                        "Theta估算(每日)": greeks.theta_per_day if greeks else None,
                        "Vega估算(每1%)": greeks.vega_per_pct if greeks else None,
                        "|Delta|": abs(greeks.delta) if greeks else None,
                        "DTE": dte,
                        "年化報酬率": annual_return,
                        "年化本金": capital_basis,
                        "成交量": quote.volume,
                        "未平倉": quote.open_interest,
                        "Delta條件結果": evaluation.delta_result,
                        "Bid-Ask價差條件結果": evaluation.spread_result,
                        "年化報酬率條件結果": evaluation.annual_return_result,
                        "未平倉條件結果": evaluation.open_interest_result,
                        "全部條件符合": overall_result,
                        "通知狀態": alert.status,
                        "可再次通知": alert.armed,
                        "連續有效不符合": alert.consecutive_nonmatches,
                        "待寄信": "新符合" if alert.pending_email else "",
                        "最後成交時間": quote.last_trade_time,
                        "最後抓取時間": now,
                        "資料狀態": "；".join(data_issues) if data_issues else "正常",
                    }
                    rows.append(row)
                    if alert.pending_email:
                        new_alerts.append(
                            {
                                "contract_symbol": quote.contract_symbol,
                                "option_type": quote.option_type,
                                "strike": quote.strike,
                                "bid": seller_price,
                                "ask": quote.ask,
                                "spread_rate": spread_rate,
                                "delta": greeks.delta if greeks else None,
                                "gamma": greeks.gamma if greeks else None,
                                "theta": greeks.theta_per_day if greeks else None,
                                "vega": greeks.vega_per_pct if greeks else None,
                                "annual_return": annual_return,
                                "open_interest": quote.open_interest,
                                "dte": dte,
                                "last_fetch": now.isoformat(),
                            }
                        )

                chain_rows[scan.scan_id] = rows
                pending_email = _merge_pending(
                    scan.values.get("待寄信"), new_alerts, now
                )
                if not quotes:
                    scan_data_status = "期權鍊無資料"
                elif any(row["資料狀態"] != "正常" for row in rows):
                    scan_data_status = "部分資料不足"
                else:
                    scan_data_status = "正常"
                updates[scan.scan_id] = {
                    "狀態": "掃描中" if scan.has_active_conditions else "僅顯示期權鍊",
                    "標的股價": snapshot.underlying_price,
                    "合約數": len(rows),
                    "符合數": matching_count,
                    "最後抓取時間": now,
                    "資料狀態": scan_data_status,
                    "待寄信": pending_email,
                    "錯誤訊息": "",
                    "工作表": scan.sheet_name,
                    "已建立基準": True,
                    "條件指紋": scan.condition_fingerprint,
                }
                success_count += 1
                contract_count += len(rows)

        self.repository.update_scan_outputs(headers, scans, updates)
        self.repository.write_chain_sheets(scans, chain_rows)

        close_trend_count = 0
        if capture_close_trend and close_time is not None:
            trend_rows = build_close_trend_rows(
                scans=active,
                chain_rows=chain_rows,
                scan_updates=updates,
                market_close=close_time,
                captured_at=now,
                market_timezone=market_timezone,
                risk_free_rate_source=risk_free_rate_source,
            )
            self.repository.upsert_close_trend_rows(trend_rows)
            close_trend_count = len(trend_rows)

        if rate_limit_error:
            return self._rate_limited(settings, now, rate_limit_error, already_written=True)

        status = "成功" if error_count == 0 else "部分成功"
        self.repository.update_settings(
            {
                "連續失敗次數": 0,
                "下次允許抓取(UTC)": "",
                "最後成功抓取(UTC)": now.isoformat(),
                "最後執行(UTC)": now.isoformat(),
                "最後狀態": status,
            }
        )
        self.repository.append_system_log(
            "INFO",
            status,
            json.dumps(
                {
                    "scans": success_count,
                    "contracts": contract_count,
                    "errors": error_count,
                    "invalid_rows": invalid_rows,
                    "market_open": is_open,
                    "close_update": session.just_closed,
                    "close_trend_rows": close_trend_count,
                    "risk_free_rate": risk_free_rate,
                    "risk_free_rate_source": risk_free_rate_source,
                },
                ensure_ascii=False,
            ),
        )
        return {
            "status": status,
            "scans": success_count,
            "contracts": contract_count,
            "errors": error_count,
            "invalid_rows": invalid_rows,
            "market_open": is_open,
            "close_update": session.just_closed,
            "close_trend_rows": close_trend_count,
            "risk_free_rate": risk_free_rate,
            "risk_free_rate_source": risk_free_rate_source,
        }

    def _error_update(
        self, scan: ScanRecord, now: datetime, status: str, message: str
    ) -> dict[str, Any]:
        return {
            "狀態": "錯誤",
            "最後抓取時間": now,
            "資料狀態": status,
            "錯誤訊息": message[:1000],
            "工作表": scan.sheet_name,
        }

    def _rate_limited(
        self,
        settings: dict[str, Any],
        now: datetime,
        message: str,
        already_written: bool = False,
    ) -> dict[str, Any]:
        failures = _as_int(settings.get("連續失敗次數"), 0) + 1
        delay_minutes = min(15 * (2 ** (failures - 1)), 60)
        next_allowed = now + timedelta(minutes=delay_minutes)
        self.repository.update_settings(
            {
                "連續失敗次數": failures,
                "下次允許抓取(UTC)": next_allowed.isoformat(),
                "最後執行(UTC)": now.isoformat(),
                "最後狀態": "Yahoo 流量限制",
            }
        )
        self.repository.append_system_log("WARN", "Yahoo 流量限制", message)
        return {
            "status": "rate_limited",
            "next_allowed": next_allowed.isoformat(),
            "already_written": already_written,
        }

    def _skip(
        self, reason: str, now: datetime, next_run: datetime | None
    ) -> dict[str, Any]:
        self.repository.update_settings(
            {"最後執行(UTC)": now.isoformat(), "最後狀態": reason}
        )
        result = {"status": "skipped", "reason": reason}
        if next_run is not None:
            result["next_run"] = next_run.isoformat()
        return result
