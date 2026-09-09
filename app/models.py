from __future__ import annotations

import hashlib
import json
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
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def normalize_display_type(value: Any) -> str:
    text = str(value or "ALL").strip().upper()
    return {"全部": "ALL", "BOTH": "ALL", "買權": "CALL", "賣權": "PUT"}.get(text, text)


def normalize_comparator(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "")
    return {">=": "≥", "=>": "≥", "大於等於": "≥", "<=": "≤", "=<": "≤", "小於等於": "≤"}.get(text, text)


def parse_sheet_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return date(1899, 12, 30) + timedelta(days=int(float(value)))
    text = str(value or "").strip()
    for candidate in (text[:10], text):
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    raise ValueError("到期日必須是 YYYY-MM-DD")


def _paired_condition(values: dict[str, Any], operator_header: str, threshold_header: str) -> tuple[str, float | None]:
    operator = normalize_comparator(values.get(operator_header))
    raw = values.get(threshold_header)
    threshold = as_optional_float(raw)
    if bool(operator) != (raw not in (None, "")):
        raise ValueError(f"{operator_header}與{threshold_header}必須同時填寫或同時留空")
    if not operator:
        return "", None
    if operator not in {"≥", "≤"}:
        raise ValueError(f"{operator_header}必須是 ≥ 或 ≤")
    if threshold is None or threshold < 0:
        raise ValueError(f"{threshold_header}必須是大於或等於 0 的數字")
    return operator, threshold


@dataclass(slots=True, frozen=True)
class ThresholdConditions:
    enabled: bool
    delta_operator: str = ""
    delta_threshold: float | None = None
    spread_operator: str = ""
    spread_threshold: float | None = None
    annual_return_operator: str = ""
    annual_return_threshold: float | None = None
    open_interest_min: float | None = None

    @property
    def has_active_conditions(self) -> bool:
        return any(value is not None for value in (
            self.delta_threshold, self.spread_threshold, self.annual_return_threshold, self.open_interest_min
        ))

    def fingerprint(self, *, display_type: str, call_cost_basis: float | None) -> str:
        payload = {
            "enabled": self.enabled, "display_type": display_type,
            "delta": [self.delta_operator, self.delta_threshold],
            "spread": [self.spread_operator, self.spread_threshold],
            "annual": [self.annual_return_operator, self.annual_return_threshold],
            "open_interest": self.open_interest_min, "call_cost_basis": call_cost_basis,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _parse_threshold(values: dict[str, Any], prefix: str) -> ThresholdConditions:
    delta_op, delta = _paired_condition(values, f"{prefix}Delta條件", f"{prefix}Delta門檻")
    if delta is not None and delta > 1:
        raise ValueError(f"{prefix}Delta門檻必須介於 0 與 1")
    spread_op, spread = _paired_condition(values, f"{prefix}Bid-Ask價差條件", f"{prefix}Bid-Ask價差門檻")
    annual_op, annual = _paired_condition(values, f"{prefix}年化報酬率條件", f"{prefix}年化報酬率門檻")
    oi = as_optional_float(values.get(f"{prefix}未平倉大於(口)"))
    if values.get(f"{prefix}未平倉大於(口)") not in (None, "") and (oi is None or oi < 0):
        raise ValueError(f"{prefix}未平倉口數必須大於或等於 0")
    result = ThresholdConditions(as_bool(values.get(f"{prefix}門檻啟用")), delta_op, delta, spread_op, spread, annual_op, annual, oi)
    if result.enabled and not result.has_active_conditions:
        raise ValueError(f"{prefix}門檻已啟用，但至少要設定一個條件")
    return result


@dataclass(slots=True)
class ScanRecord:
    row_number: int
    values: dict[str, Any]
    enabled: bool
    scan_id: str
    ticker: str
    expiry: date
    display_type: str
    first_threshold: ThresholdConditions
    second_threshold: ThresholdConditions
    call_cost_basis: float | None
    email_enabled: bool
    note: str = ""

    @property
    def sheet_name(self) -> str:
        safe = "".join(c for c in self.ticker if c.isalnum() or c in ".-_")
        return f"{safe}_{self.expiry.isoformat()}"[:100]

    @property
    def first_condition_fingerprint(self) -> str:
        return self.first_threshold.fingerprint(display_type=self.display_type, call_cost_basis=self.call_cost_basis)

    @property
    def second_condition_fingerprint(self) -> str:
        return self.second_threshold.fingerprint(display_type=self.display_type, call_cost_basis=self.call_cost_basis)

    @classmethod
    def from_values(cls, row_number: int, headers: list[str], row: list[Any]) -> "ScanRecord":
        padded = row + [""] * max(0, len(headers) - len(row))
        values = dict(zip(headers, padded))
        ticker = str(values.get("股票代號", "")).strip().upper()
        if not ticker:
            raise ValueError("股票代號不可空白")
        expiry = parse_sheet_date(values.get("到期日"))
        display_type = normalize_display_type(values.get("顯示類型"))
        if display_type not in {"ALL", "CALL", "PUT"}:
            raise ValueError("顯示類型必須是 ALL、CALL 或 PUT")
        cost = as_optional_float(values.get("CALL持股成本"))
        if values.get("CALL持股成本") not in (None, "") and (cost is None or cost <= 0):
            raise ValueError("CALL持股成本必須大於 0")
        scan_id = str(values.get("掃描ID", "")).strip() or f"{ticker}|{expiry.isoformat()}"
        return cls(row_number, values, as_bool(values.get("啟用")), scan_id, ticker, expiry, display_type,
                   _parse_threshold(values, "第一"), _parse_threshold(values, "第二"), cost,
                   as_bool(values.get("Email通知")), str(values.get("備註", "")))


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
    dividend_yield_note: str = ""


@dataclass(slots=True, frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega_per_pct: float
    theta_per_day: float
    dte: int


@dataclass(slots=True, frozen=True)
class ConditionEvaluation:
    enabled: bool
    has_active_conditions: bool
    matched: bool | None
    delta_result: str
    spread_result: str
    annual_return_result: str
    open_interest_result: str


@dataclass(slots=True, frozen=True)
class ContractAlertDecision:
    status: str
    armed: bool
    consecutive_nonmatches: int
    pending_email: bool
    sequence: int
