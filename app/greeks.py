from __future__ import annotations

import math
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from .models import Greeks


SECONDS_PER_YEAR = 365.0 * 24 * 60 * 60


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def time_to_expiry_years(
    expiry: date,
    now: datetime | None = None,
    market_timezone: str = "America/New_York",
) -> tuple[float, int]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    zone = ZoneInfo(market_timezone)
    local_now = now.astimezone(zone)
    expiry_close = datetime.combine(expiry, time(16, 0), tzinfo=zone)
    seconds = max(0.0, (expiry_close - local_now).total_seconds())
    dte = max(0, (expiry - local_now.date()).days)
    return seconds / SECONDS_PER_YEAR, dte


def calculate_greeks(
    *,
    option_type: str,
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    expiry: date,
    now: datetime | None = None,
    market_timezone: str = "America/New_York",
) -> Greeks | None:
    """Black-Scholes-Merton estimates; Vega is per 1 volatility percentage point."""
    if spot <= 0 or strike <= 0 or volatility <= 0:
        return None
    years, dte = time_to_expiry_years(expiry, now, market_timezone)
    if years <= 0:
        return None

    sqrt_t = math.sqrt(years)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * years
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount_r = math.exp(-risk_free_rate * years)
    discount_q = math.exp(-dividend_yield * years)
    density = _norm_pdf(d1)

    option_type = option_type.upper()
    common_theta = -(spot * discount_q * density * volatility) / (2.0 * sqrt_t)
    if option_type == "CALL":
        delta = discount_q * _norm_cdf(d1)
        theta_annual = (
            common_theta
            - risk_free_rate * strike * discount_r * _norm_cdf(d2)
            + dividend_yield * spot * discount_q * _norm_cdf(d1)
        )
    elif option_type == "PUT":
        delta = discount_q * (_norm_cdf(d1) - 1.0)
        theta_annual = (
            common_theta
            + risk_free_rate * strike * discount_r * _norm_cdf(-d2)
            - dividend_yield * spot * discount_q * _norm_cdf(-d1)
        )
    else:
        raise ValueError("option_type must be CALL or PUT")

    vega_per_pct = spot * discount_q * density * sqrt_t / 100.0
    return Greeks(
        delta=delta,
        vega_per_pct=vega_per_pct,
        theta_per_day=theta_annual / 365.0,
        dte=dte,
    )

