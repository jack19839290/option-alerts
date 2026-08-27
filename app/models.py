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
    aliases = {"全部": "ALL", "BOTH": "ALL", "買權": "CALL", "賣權": "PUT"}
    return aliases.get(text, text)


def normalize_comparator(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "")
    aliases = {
        ">=": "≥",
        "=>": "≥",
        "大於等於": "≥",
        "<=": "≤",
        "=<": "≤",
        "小於等於": "≤",
    }
    return aliases.get(text, text)


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


def _paired_condition(
    values: dict[str, Any], operator_header: str, threshold_header: str
) -> tuple[str, float | None]:
    operator = normalize_comparator(values.get(operator_header))
    threshold_raw = values.get(threshold_header)
    threshold = as_optional_float(threshold_raw)
    has_operator = bool(operator)
    has_threshold = threshold_raw not in (None, "")
    if has_operator != has_threshold:
        raise ValueError(f"{operator_header}與{threshold_header}必須同時填寫或同時留空")
    if not has_operator:
        return "", None
    if operator not in {"≥", "≤"}:
        raise ValueError(f"{operator_header}必須是 ≥ 或 ≤")
    if threshold is None or threshold < 0:
        raise ValueError(f"{threshold_header}必須是大於或等於 0 的數字")
    return operator, threshold


@dataclass(slots=True)
class ScanRecord:
    row_number: int
    values: dict[str, Any]
    enabled: bool
    scan_id: str
    ticker: str
    expiry: date
    display_type: str
    delta_operator: str
    delta_threshold: float | None
    vega_operator: str
    vega_threshold: float | None
    annual_return_operator: str
    annual_return_threshold: float | None
    call_cost_basis: float | None
    open_interest_min: float | None
    email_enabled: bool
    note: str = ""
    baseline_established: bool = False

    @property
    def sheet_name(self) -> str:
        safe_ticker = "".join(c for c in self.ticker if c.isalnum() or c in ".-_")
        return f"{safe_ticker}_{self.expiry.isoformat()}"[:100]

    @property
    def has_active_conditions(self) -> bool:
        return any(
            threshold is not None
            for threshold in (
                self.delta_threshold,
                self.vega_threshold,
                self.annual_return_threshold,
                self.open_interest_min,
            )
        )

    @property
    def condition_fingerprint(self) -> str:
        payload = {
            "display_type": self.display_type,
            "delta": [self.delta_operator, self.delta_threshold],
            "vega": [self.vega_operator, self.vega_threshold],
            "annual_return": [
                self.annual_return_operator,
                self.annual_return_threshold,
            ],
            "call_cost_basis": self.call_cost_basis,
            "open_interest_min": self.open_interest_min,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_values(
        cls, row_number: int, headers: list[str], row: list[Any]
    ) -> "ScanRecord":
        padded = row + [""] * max(0, len(headers) - len(row))
        values = dict(zip(headers, padded))
        ticker = str(values.get("股票代號", "")).strip().upper()
        if not ticker:
            raise ValueError("股票代號不可空白")
        expiry = parse_sheet_date(values.get("到期日"))
        display_type = normalize_display_type(values.get("顯示類型"))
        if display_type not in {"ALL", "CALL", "PUT"}:
            raise ValueError("顯示類型必須是 ALL、CALL 或 PUT")

        delta_operator, delta_threshold = _paired_condition(
            values, "Delta條件", "Delta門檻"
        )
        if delta_threshold is not None and delta_threshold > 1:
            raise ValueError("Delta門檻必須介於 0 與 1")
        vega_operator, vega_threshold = _paired_condition(
            values, "Vega條件", "Vega門檻"
        )
        annual_operator, annual_threshold = _paired_condition(
            values, "年化報酬率條件", "年化報酬率門檻"
        )

        call_cost_basis = as_optional_float(values.get("CALL持股成本"))
        if values.get("CALL持股成本") not in (None, "") and (
            call_cost_basis is None or call_cost_basis <= 0
        ):
            raise ValueError("CALL持股成本必須大於 0")
        open_interest_min = as_optional_float(values.get("未平倉大於(口)"))
        if values.get("未平倉大於(口)") not in (None, "") and (
            open_interest_min is None or open_interest_min < 0
        ):
            raise ValueError("未平倉口數必須大於或等於 0")

        scan_id = str(values.get("掃描ID", "")).strip()
        if not scan_id:
            scan_id = f"{ticker}|{expiry.isoformat()}"
        return cls(
            row_number=row_number,
            values=values,
            enabled=as_bool(values.get("啟用")),
            scan_id=scan_id,
            ticker=ticker,
            expiry=expiry,
            display_type=display_type,
            delta_operator=delta_operator,
            delta_threshold=delta_threshold,
            vega_operator=vega_operator,
            vega_threshold=vega_threshold,
            annual_return_operator=annual_operator,
            annual_return_threshold=annual_threshold,
            call_cost_basis=call_cost_basis,
            open_interest_min=open_interest_min,
            email_enabled=as_bool(values.get("Email通知")),
            note=str(values.get("備註", "")),
            baseline_established=as_bool(values.get("已建立基準")),
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
    dividend_yield_note: str = ""


@dataclass(slots=True, frozen=True)
class Greeks:
    delta: float
    vega_per_pct: float
    theta_per_day: float
    dte: int


@dataclass(slots=True, frozen=True)
class ConditionEvaluation:
    has_active_conditions: bool
    matched: bool | None
    delta_result: str
    vega_result: str
    annual_return_result: str
    open_interest_result: str


@dataclass(slots=True, frozen=True)
class ContractAlertDecision:
    status: str
    armed: bool
    consecutive_nonmatches: int
    pending_email: bool
