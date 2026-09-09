from __future__ import annotations

from .models import ConditionEvaluation, ContractAlertDecision, ThresholdConditions

DISABLED = "停用"
MATCHED = "符合"
NOT_MATCHED = "未符合"
NO_CONDITIONS = "尚未設定條件"
INSUFFICIENT = "資料不足"


def _condition_result(value: float | int | None, operator: str, threshold: float | None) -> tuple[str, bool, bool]:
    if threshold is None:
        return "未設定", True, True
    if value is None:
        return INSUFFICIENT, False, False
    passed = value >= threshold if operator == "≥" else value <= threshold if operator == "≤" else False
    return ("通過" if passed else "未通過"), passed, operator in {"≥", "≤"}


def evaluate_conditions(*, conditions: ThresholdConditions, delta: float | None,
                        spread_rate: float | None, annual_return: float | None,
                        open_interest: int | None) -> ConditionEvaluation:
    if not conditions.enabled:
        return ConditionEvaluation(False, conditions.has_active_conditions, False, "停用", "停用", "停用", "停用")
    delta_result = _condition_result(abs(delta) if delta is not None else None, conditions.delta_operator, conditions.delta_threshold)
    spread_result = _condition_result(spread_rate, conditions.spread_operator, conditions.spread_threshold)
    annual_result = _condition_result(annual_return, conditions.annual_return_operator, conditions.annual_return_threshold)
    if conditions.open_interest_min is None:
        oi_result = ("未設定", True, True)
    elif open_interest is None:
        oi_result = (INSUFFICIENT, False, False)
    else:
        passed = open_interest > conditions.open_interest_min
        oi_result = ("通過" if passed else "未通過", passed, True)
    results = (delta_result, spread_result, annual_result, oi_result)
    matched = None if not all(x[2] for x in results) else all(x[1] for x in results)
    return ConditionEvaluation(True, conditions.has_active_conditions, matched,
                               delta_result[0], spread_result[0], annual_result[0], oi_result[0])


def overall_result(evaluation: ConditionEvaluation) -> str:
    if not evaluation.enabled:
        return "未啟用"
    if not evaluation.has_active_conditions:
        return NO_CONDITIONS
    if evaluation.matched is None:
        return INSUFFICIENT
    return MATCHED if evaluation.matched else NOT_MATCHED


def evaluate_contract_alert(*, evaluation: ConditionEvaluation, previous_armed: bool | None,
                            previous_nonmatches: int, previous_sequence: int,
                            email_enabled: bool) -> ContractAlertDecision:
    sequence = max(1, previous_sequence or 1)
    if not evaluation.enabled:
        return ContractAlertDecision(DISABLED, True, 0, False, sequence)
    if not evaluation.has_active_conditions:
        return ContractAlertDecision(NO_CONDITIONS, True, 0, False, sequence)
    if evaluation.matched is None:
        return ContractAlertDecision(INSUFFICIENT, True if previous_armed is None else previous_armed,
                                     max(0, previous_nonmatches), False, sequence)
    if evaluation.matched:
        armed = True if previous_armed is None else previous_armed
        return ContractAlertDecision("新符合" if armed else "持續符合", False, 0,
                                     bool(armed and email_enabled), sequence)
    count = max(0, previous_nonmatches) + 1
    was_armed = bool(previous_armed)
    armed = was_armed or count >= 2
    if armed and not was_armed:
        sequence += 1
    return ContractAlertDecision(NOT_MATCHED, armed, count, False, sequence)
