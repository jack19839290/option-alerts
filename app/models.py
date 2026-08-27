from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "是", "啟用"}


def as_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number


def normalize_option_type(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"C", "CALL", "買權"}:
        return "CALL"
    if text in {"P", "PUT", "賣權"}:
        return "PUT"
    return text


def format_strike(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def parse_sheet_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Google Sheets/Excel serial dates use 1899-12-30 as day zero.
        return date(1899, 12, 30) + timedelta(days=int(float(value)))

    text = str(value or "").strip()
    for candidate in (text[:10], text):
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    raise ValueError("到期日必須是 YYYY-MM-DD")


@dataclass(slots=True)
class MonitorRecord:
    row_number: int
    values: dict[str, Any]
    enabled: bool
    monitor_id: str
    ticker: str
    expiry: date
    option_type: str
    strike: float
    low_threshold: float | None
    high_threshold: float | None
    email_enabled: bool
    note: str = ""

    @property
    def sheet_name(self) -> str:
        safe_ticker = "".join(c for c in self.ticker if c.isalnum() or c in ".-_")
        return f"{safe_ticker}_{self.expiry.isoformat()}"[:100]

    @classmethod
    def from_values(
        cls, row_number: int, headers: list[str], row: list[Any]
    ) -> "MonitorRecord":
        padded = row + [""] * max(0, len(headers) - len(row))
        values = dict(zip(headers, padded))
        ticker = str(values.get("股票代號", "")).strip().upper()
        option_type = normalize_option_type(values.get("類型"))
        strike = as_optional_float(values.get("履約價"))
        if not ticker:
            raise ValueError("股票代號不可空白")
        if option_type not in {"CALL", "PUT"}:
            raise ValueError("類型必須是 CALL 或 PUT")
        if strike is None or strike <= 0:
            raise ValueError("履約價必須大於 0")
        expiry = parse_sheet_date(values.get("到期日"))
        low = as_optional_float(values.get("低於警示"))
        high = as_optional_float(values.get("高於警示"))
        monitor_id = str(values.get("監控ID", "")).strip()
        if not monitor_id:
            monitor_id = f"{ticker}|{expiry.isoformat()}|{option_type}|{format_strike(strike)}"
        return cls(
            row_number=row_number,
            values=values,
            enabled=as_bool(values.get("啟用")),
            monitor_id=monitor_id,
            ticker=ticker,
            expiry=expiry,
            option_type=option_type,
            strike=strike,
            low_threshold=low,
            high_threshold=high,
            email_enabled=as_bool(values.get("Email通知")),
            note=str(values.get("備註", "")),
        )


@dataclass(slots=True)
class OptionQuote:
    contract_symbol: str
    option_type: str
    strike: float
    last_price: float | None
    bid: float | None
    ask: float | None
    implied_volatility: float | None
    volume: int | None
    open_interest: int | None
    last_trade_time: datetime | None


@dataclass(slots=True)
class ChainSnapshot:
    ticker: str
    expiry: date
    underlying_price: float | None
    dividend_yield: float
    quotes: list[OptionQuote] = field(default_factory=list)

    def find(self, option_type: str, strike: float) -> OptionQuote | None:
        for quote in self.quotes:
            if quote.option_type == option_type and abs(quote.strike - strike) < 1e-6:
                return quote
        return None


@dataclass(slots=True, frozen=True)
class Greeks:
    delta: float
    vega_per_pct: float
    theta_per_day: float
    dte: int


@dataclass(slots=True, frozen=True)
class AlertDecision:
    state: str
    pending_email: str
    rearmed: bool = False
