from __future__ import annotations

import math
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .constants import CLOSE_TREND_TARGETS
from .models import ScanRecord


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _option_types(scan: ScanRecord) -> tuple[str, ...]:
    if scan.display_type == "ALL":
        return ("CALL", "PUT")
    return (scan.display_type,)


def resolve_market_close(
    *, now: datetime, market_close: datetime | None, market_timezone: str
) -> datetime:
    """Return the official close in UTC, falling back to 16:00 local time."""
    if market_close is not None:
        return market_close.astimezone(timezone.utc)
    zone = ZoneInfo(market_timezone)
    local_now = now.astimezone(zone)
    local_close = datetime.combine(local_now.date(), time(16, 0), tzinfo=zone)
    return local_close.astimezone(timezone.utc)


def select_delta_candidate(
    rows: list[dict[str, Any]], option_type: str, target_delta: float
) -> dict[str, Any] | None:
    """Pick the closest absolute Delta that does not exceed the target."""
    candidates: list[tuple[float, float, float, str, dict[str, Any]]] = []
    for row in rows:
        if str(row.get("類型") or "").upper() != option_type:
            continue
        absolute_delta = _optional_float(row.get("|Delta|"))
        if absolute_delta is None or absolute_delta < 0:
            continue
        if absolute_delta > target_delta + 1e-12:
            continue
        spread = _optional_float(row.get("Bid-Ask價差率"))
        open_interest = _optional_float(row.get("未平倉"))
        candidates.append(
            (
                -absolute_delta,
                spread if spread is not None and spread >= 0 else math.inf,
                -(open_interest if open_interest is not None else -1),
                str(row.get("合約代號") or ""),
                row,
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    return candidates[0][4]


def _premium_return(row: dict[str, Any]) -> float | None:
    premium = _optional_float(row.get("賣出試算價"))
    capital = _optional_float(row.get("年化本金"))
    if premium is None or premium <= 0 or capital is None or capital <= 0:
        return None
    return premium / capital


def volatility_summary(rows: list[dict[str, Any]], option_type: str) -> dict[str, Any]:
    """Same-expiry, same-side IV interpolation; never extrapolate missing wings."""
    valid = []
    for row in rows:
        iv, bid, ask, spot, strike, dte = (
            _optional_float(row.get(key))
            for key in ("IV", "Bid", "Ask", "標的股價", "履約價", "DTE")
        )
        if (row.get("類型") != option_type or row.get("資料狀態") != "正常"
                or any(x is None for x in (iv, bid, ask, spot, strike, dte))):
            continue
        if iv <= 0.00001 or bid <= 0 or ask < bid or spot <= 0 or strike <= 0 or dte <= 0:
            continue
        valid.append(row)

    def sample(key: str, target: float, candidates: list[dict[str, Any]]) -> tuple[float | None, str]:
        points = {}
        # Tightest spread then symbol gives a deterministic duplicate choice.
        for row in sorted(candidates, key=lambda r: (
            (r["Ask"] - r["Bid"]) / ((r["Ask"] + r["Bid"]) / 2),
            str(r.get("合約代號", "")),
        )):
            x = _optional_float(row.get(key))
            if x is not None:
                points.setdefault(x, row)
        exact = next((x for x in points if abs(x - target) < 1e-12), None)
        if exact is not None:
            row = points[exact]
            return float(row["IV"]), str(row.get("合約代號", ""))
        lower = max((x for x in points if x < target), default=None)
        upper = min((x for x in points if x > target), default=None)
        if lower is None or upper is None:
            return None, "缺少有效包夾合約"
        left, right = points[lower], points[upper]
        weight = (target - lower) / (upper - lower)
        value = float(left["IV"]) * (1 - weight) + float(right["IV"]) * weight
        return value, f"內插 {left.get('合約代號', '')}/{right.get('合約代號', '')} ({lower:.4f}/{upper:.4f})"

    otm = [r for r in valid if (
        r["履約價"] <= r["標的股價"] if option_type == "PUT"
        else r["履約價"] >= r["標的股價"]
    ) and 0 < (_optional_float(r.get("|Delta|")) or 0) < 1]
    iv10, note10 = sample("|Delta|", 0.10, otm)
    iv25, note25 = sample("|Delta|", 0.25, otm)
    atm, note_atm = sample("履約價", float(valid[0]["標的股價"]), valid) if valid else (None, "無有效資料")
    return {
        "10Δ IV": iv10, "25Δ IV": iv25, "ATM IV": atm,
        "10Δ − 25Δ": (iv10 - iv25) * 100 if iv10 is not None and iv25 is not None else None,
        "10Δ − ATM": (iv10 - atm) * 100 if iv10 is not None and atm is not None else None,
        "IV取樣說明": f"{option_type}同到期日；10Δ: {note10}；25Δ: {note25}；ATM: {note_atm}；差值單位：波動率點",
    }


def _base_row(
    *,
    scan: ScanRecord,
    option_type: str,
    target_delta: float,
    market_close: datetime,
    captured_at: datetime,
    market_timezone: str,
) -> dict[str, Any]:
    market_date = market_close.astimezone(ZoneInfo(market_timezone)).date().isoformat()
    target_key = f"{target_delta:.2f}"
    return {
        "快照ID": f"{market_date}|{scan.scan_id}|{option_type}|{target_key}",
        "美東交易日": market_date,
        "官方收盤時間(UTC)": market_close.astimezone(timezone.utc),
        "實際抓取時間(UTC)": captured_at.astimezone(timezone.utc),
        "掃描ID": scan.scan_id,
        "股票代號": scan.ticker,
        "到期日": scan.expiry,
        "類型": option_type,
        "目標|Delta|": target_delta,
    }


def build_close_trend_rows(
    *,
    scans: list[ScanRecord],
    chain_rows: dict[str, list[dict[str, Any]]],
    scan_updates: dict[str, dict[str, Any]],
    market_close: datetime,
    captured_at: datetime,
    market_timezone: str,
    risk_free_rate_source: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for scan in scans:
        if not scan.enabled:
            continue
        rows = chain_rows.get(scan.scan_id)
        update = scan_updates.get(scan.scan_id, {})
        for option_type in _option_types(scan):
            type_rows = (
                []
                if rows is None
                else [row for row in rows if row.get("類型") == option_type]
            )
            for target_delta in CLOSE_TREND_TARGETS:
                output = _base_row(
                    scan=scan,
                    option_type=option_type,
                    target_delta=target_delta,
                    market_close=market_close,
                    captured_at=captured_at,
                    market_timezone=market_timezone,
                )
                selected = (
                    None
                    if rows is None
                    else select_delta_candidate(rows, option_type, target_delta)
                )
                if selected is None:
                    if rows is None:
                        status = str(update.get("資料狀態") or "未執行")
                        note = str(update.get("錯誤訊息") or status)
                    elif not type_rows:
                        status = "期權鍊無資料"
                        note = f"{option_type} 沒有可用合約"
                    elif not any(_optional_float(row.get("|Delta|")) is not None for row in type_rows):
                        status = "Greeks不足"
                        note = f"{option_type} 合約皆缺少有效 Delta"
                    else:
                        status = "無符合合約"
                        note = f"沒有 |Delta| 不超過 {target_delta:.2f} 的 {option_type} 合約"
                    output.update(
                        {
                            "選取狀態": status,
                            "資料狀態": status,
                            "備註／未選取原因": note[:1000],
                        }
                    )
                    result.append(output)
                    continue

                absolute_delta = _optional_float(selected.get("|Delta|"))
                output.update(
                    {
                        "選取狀態": "已選取",
                        "合約代號": selected.get("合約代號"),
                        "履約價": selected.get("履約價"),
                        "Delta估算": selected.get("Delta估算"),
                        "|Delta|": absolute_delta,
                        "Delta差距": (
                            target_delta - absolute_delta
                            if absolute_delta is not None
                            else None
                        ),
                        "標的快照價": selected.get("標的股價"),
                        "Last": selected.get("Last"),
                        "Bid": selected.get("Bid"),
                        "Ask": selected.get("Ask"),
                        "Mid": selected.get("Mid"),
                        "Bid-Ask價差率": selected.get("Bid-Ask價差率"),
                        "賣出試算價": selected.get("賣出試算價"),
                        "試算價來源": selected.get("試算價來源"),
                        "年化本金": selected.get("年化本金"),
                        "DTE": selected.get("DTE"),
                        "到期權利金報酬率": _premium_return(selected),
                        "年化報酬率": selected.get("年化報酬率"),
                        "IV": selected.get("IV"),
                        "Gamma估算": selected.get("Gamma估算"),
                        "Theta估算(每日)": selected.get("Theta估算(每日)"),
                        "Vega估算(每1%)": selected.get("Vega估算(每1%)"),
                        "成交量": selected.get("成交量"),
                        "未平倉": selected.get("未平倉"),
                        "最後成交時間": selected.get("最後成交時間"),
                        "無風險利率": selected.get("無風險利率"),
                        "無風險利率來源": risk_free_rate_source,
                        "股息殖利率": selected.get("股息殖利率"),
                        "Greeks模型": selected.get("Greeks模型"),
                        "資料狀態": selected.get("資料狀態") or "正常",
                        "備註／未選取原因": "",
                        "標的－履約價差": (
                            _optional_float(selected.get("標的股價"))
                            - _optional_float(selected.get("履約價"))
                            if _optional_float(selected.get("標的股價")) is not None
                            and _optional_float(selected.get("履約價")) is not None
                            else None
                        ),
                        "標的－履約價差率": (
                            (
                                _optional_float(selected.get("標的股價"))
                                - _optional_float(selected.get("履約價"))
                            )
                            / _optional_float(selected.get("標的股價"))
                            if _optional_float(selected.get("標的股價")) not in (None, 0)
                            and _optional_float(selected.get("履約價")) is not None
                            else None
                        ),
                    }
                )
                result.append(output)
    return result


def build_volatility_trend_rows(*, scans, chain_rows, scan_updates, market_close,
                               captured_at, market_timezone):
    market_date = market_close.astimezone(ZoneInfo(market_timezone)).date().isoformat()
    result = []
    for scan in scans:
        if not scan.enabled:
            continue
        rows = chain_rows.get(scan.scan_id, [])
        for side in _option_types(scan):
            summary = volatility_summary(rows, side)
            complete = all(summary[key] is not None for key in ("10Δ IV", "25Δ IV", "ATM IV"))
            spot = next((_optional_float(r.get("標的股價")) for r in rows
                         if _optional_float(r.get("標的股價")) is not None), None)
            result.append({
                "快照ID": f"{market_date}|{scan.scan_id}|{side}",
                "美東交易日": market_date, "股票代號": scan.ticker, "到期日": scan.expiry,
                "類型": side, "DTE": (scan.expiry - market_close.astimezone(ZoneInfo(market_timezone)).date()).days,
                "標的快照價": spot, **summary,
                "資料狀態": "正常" if complete else (scan_updates.get(scan.scan_id, {}).get("錯誤訊息") or "IV資料不足"),
                "官方收盤時間(UTC)": market_close.astimezone(timezone.utc),
                "實際抓取時間(UTC)": captured_at.astimezone(timezone.utc),
            })
    return result
