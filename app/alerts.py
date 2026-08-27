from __future__ import annotations

from .models import AlertDecision


NORMAL = "正常"
HIGH = "高於上限"
LOW = "低於下限"
INSUFFICIENT = "資料不足"
DISABLED = "停用"


def evaluate_alert(
    *,
    price: float | None,
    low_threshold: float | None,
    high_threshold: float | None,
    previous_state: str,
    email_enabled: bool,
    hysteresis: float = 0.02,
) -> AlertDecision:
    if price is None:
        return AlertDecision(INSUFFICIENT, "")

    previous_state = previous_state or NORMAL
    hysteresis = max(0.0, hysteresis)

    if previous_state == HIGH and high_threshold is not None:
        if price > high_threshold * (1.0 - hysteresis):
            return AlertDecision(HIGH, "")
        previous_state = NORMAL
    elif previous_state == LOW and low_threshold is not None:
        if price < low_threshold * (1.0 + hysteresis):
            return AlertDecision(LOW, "")
        previous_state = NORMAL

    if high_threshold is not None and price >= high_threshold:
        pending = HIGH if email_enabled and previous_state != HIGH else ""
        return AlertDecision(HIGH, pending)
    if low_threshold is not None and price <= low_threshold:
        pending = LOW if email_enabled and previous_state != LOW else ""
        return AlertDecision(LOW, pending)
    return AlertDecision(NORMAL, "", rearmed=previous_state in {HIGH, LOW})

