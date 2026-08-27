from __future__ import annotations

import math


def valid_price(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def select_alert_price(
    bid: float | None, ask: float | None, last_price: float | None
) -> tuple[float | None, str, float | None]:
    """Prefer midpoint; use Last only when a valid two-sided market is unavailable."""
    if valid_price(bid) and valid_price(ask) and ask >= bid:
        midpoint = (bid + ask) / 2
        return midpoint, "Mid", midpoint
    if valid_price(last_price):
        return last_price, "Last", None
    return None, "無可用價格", None

