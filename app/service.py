from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .alerts import DISABLED, evaluate_alert
from .greeks import calculate_greeks, time_to_expiry_years
from .market_clock import is_us_regular_session
from .models import MonitorRecord
from .pricing import select_alert_price
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
        is_open = is_us_regular_session(now, market_timezone)
        interval_minutes = _as_int(
            settings.get("開盤更新間隔(分鐘)" if is_open else "盤外更新間隔(分鐘)"),
            5 if is_open else 10,
        )

        next_allowed = _parse_utc(settings.get("下次允許抓取(UTC)"))
        if not force and next_allowed and now < next_allowed:
            return self._skip("退避等待中", now, next_allowed)
        last_success = _parse_utc(settings.get("最後成功抓取(UTC)"))
        if not force and last_success and now < last_success + timedelta(minutes=interval_minutes):
            return self._skip(
                "尚未到更新時間", now, last_success + timedelta(minutes=interval_minutes)
            )

        headers, monitors, invalid_rows = self.repository.load_monitors()
        active = [monitor for monitor in monitors if monitor.enabled]
        updates: dict[str, dict[str, Any]] = {}
        for monitor in monitors:
            if not monitor.enabled:
                updates[monitor.monitor_id] = {
                    "狀態": DISABLED,
                    "資料狀態": DISABLED,
                    "警示狀態": DISABLED,
                    "工作表": monitor.sheet_name,
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
            return self._rate_limited(settings, now, str(exc))

        groups: dict[tuple[str, object], list[MonitorRecord]] = defaultdict(list)
        for monitor in active:
            groups[(monitor.ticker, monitor.expiry)].append(monitor)

        success_count = 0
        error_count = len(invalid_rows)
        rate_limit_error = ""
        for (ticker, expiry), group in groups.items():
            try:
                snapshot = provider.fetch_chain(ticker, expiry)
            except RateLimitError as exc:
                rate_limit_error = str(exc)
                error_count += len(group)
                for monitor in group:
                    updates[monitor.monitor_id] = self._error_update(
                        monitor, now, "Yahoo 流量限制", str(exc)
                    )
                break
            except MarketDataError as exc:
                error_count += len(group)
                for monitor in group:
                    updates[monitor.monitor_id] = self._error_update(
                        monitor, now, "抓取失敗", str(exc)
                    )
                continue

            for monitor in group:
                quote = snapshot.find(monitor.option_type, monitor.strike)
                if quote is None:
                    error_count += 1
                    updates[monitor.monitor_id] = self._error_update(
                        monitor, now, "找不到合約", "Yahoo 期權鏈沒有此類型與履約價"
                    )
                    continue

                alert_price, price_source, midpoint = select_alert_price(
                    quote.bid, quote.ask, quote.last_price
                )
                greeks = None
                if (
                    snapshot.underlying_price is not None
                    and quote.implied_volatility is not None
                    and quote.implied_volatility > 0
                ):
                    greeks = calculate_greeks(
                        option_type=monitor.option_type,
                        spot=snapshot.underlying_price,
                        strike=monitor.strike,
                        volatility=quote.implied_volatility,
                        risk_free_rate=risk_free_rate,
                        dividend_yield=snapshot.dividend_yield,
                        expiry=monitor.expiry,
                        now=now,
                        market_timezone=market_timezone,
                    )
                _, dte = time_to_expiry_years(
                    monitor.expiry, now=now, market_timezone=market_timezone
                )
                previous_state = str(
                    monitor.values.get("上次警示狀態")
                    or monitor.values.get("警示狀態")
                    or "正常"
                )
                decision = evaluate_alert(
                    price=alert_price,
                    low_threshold=monitor.low_threshold,
                    high_threshold=monitor.high_threshold,
                    previous_state=previous_state,
                    email_enabled=monitor.email_enabled,
                    hysteresis=_as_float(settings.get("警示回復緩衝"), 0.02),
                )
                existing_pending = str(monitor.values.get("待寄信") or "").strip()
                data_status = "正常" if alert_price is not None else "報價不足"
                if greeks is None:
                    data_status = (
                        data_status + "；Greeks資料不足"
                        if data_status != "正常"
                        else "Greeks資料不足"
                    )
                updates[monitor.monitor_id] = {
                    "狀態": "監控中",
                    "合約代號": quote.contract_symbol,
                    "標的股價": snapshot.underlying_price or "",
                    "Last": quote.last_price or "",
                    "Bid": quote.bid or "",
                    "Ask": quote.ask or "",
                    "Mid": midpoint or "",
                    "警示採用價": alert_price or "",
                    "價格來源": price_source,
                    "IV": quote.implied_volatility or "",
                    "無風險利率": risk_free_rate,
                    "股息殖利率": snapshot.dividend_yield,
                    "Greeks模型": "Black-Scholes-Merton (估算)",
                    "Delta估算": greeks.delta if greeks else "",
                    "Vega估算(每1%)": greeks.vega_per_pct if greeks else "",
                    "Theta估算(每日)": greeks.theta_per_day if greeks else "",
                    "DTE": greeks.dte if greeks else dte,
                    "成交量": quote.volume if quote.volume is not None else "",
                    "未平倉": quote.open_interest if quote.open_interest is not None else "",
                    "最後成交時間": quote.last_trade_time.isoformat()
                    if quote.last_trade_time
                    else "",
                    "最後抓取時間": now.isoformat(),
                    "資料狀態": data_status,
                    "警示狀態": decision.state,
                    "待寄信": existing_pending or decision.pending_email,
                    "上次警示狀態": decision.state,
                    "錯誤訊息": "",
                    "工作表": monitor.sheet_name,
                }
                success_count += 1

        self.repository.update_monitor_outputs(headers, monitors, updates)
        self.repository.write_contract_sheets(monitors, updates)

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
                    "success": success_count,
                    "errors": error_count,
                    "invalid_rows": invalid_rows,
                    "market_open": is_open,
                },
                ensure_ascii=False,
            ),
        )
        return {
            "status": status,
            "success": success_count,
            "errors": error_count,
            "invalid_rows": invalid_rows,
            "market_open": is_open,
        }

    def _error_update(
        self, monitor: MonitorRecord, now: datetime, status: str, message: str
    ) -> dict[str, Any]:
        return {
            "狀態": "錯誤",
            "最後抓取時間": now.isoformat(),
            "資料狀態": status,
            "警示狀態": "資料不足",
            "錯誤訊息": message[:1000],
            "工作表": monitor.sheet_name,
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

    def _skip(self, reason: str, now: datetime, next_run: datetime) -> dict[str, Any]:
        self.repository.update_settings(
            {"最後執行(UTC)": now.isoformat(), "最後狀態": reason}
        )
        return {"status": "skipped", "reason": reason, "next_run": next_run.isoformat()}
