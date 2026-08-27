from __future__ import annotations

import math


def valid_price(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def calculate_mid(bid: float | None, ask: float | None) -> float | None:
    if valid_price(bid) and valid_price(ask) and ask >= bid:
        return (bid + ask) / 2
    return None


def select_alert_price(
    bid: float | None, ask: float | None, last_price: float | None
) -> tuple[float | None, str, float | None]:
    """Legacy display-price rule: prefer Mid, then Last."""
    midpoint = calculate_mid(bid, ask)
    if midpoint is not None:
        return midpoint, "Mid", midpoint
    if valid_price(last_price):
        return last_price, "Last", None
    return None, "無可用價格", None


def select_seller_price(bid: float | None) -> tuple[float | None, str]:
    """Seller return estimates use only a positive Bid."""
    if valid_price(bid):
        return bid, "Bid"
    return None, "Bid無效"


def annualized_premium_return(
    *, seller_premium: float | None, capital_basis: float | None, dte: int
) -> float | None:
    """Premium / capital / DTE * 365, returned as a decimal rate."""
    if not valid_price(seller_premium):
        return None
    if capital_basis is None or not math.isfinite(capital_basis) or capital_basis <= 0:
        return None
    if dte <= 0:
        return None
    return seller_premium / capital_basis / dte * 365.0
