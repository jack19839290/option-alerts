from __future__ import annotations

from .models import ConditionEvaluation, ContractAlertDecision, ScanRecord


DISABLED = "停用"
MATCHED = "符合"
NOT_MATCHED = "未符合"
NO_CONDITIONS = "尚未設定條件"
INSUFFICIENT = "資料不足"


def _condition_result(
    value: float | int | None, operator: str, threshold: float | None
) -> tuple[str, bool, bool]:
    if threshold is None:
        return "未設定", True, True
    if value is None:
        return INSUFFICIENT, False, False
    if operator == "≥":
        passed = value >= threshold
    elif operator == "≤":
        passed = value <= threshold
    else:
        return INSUFFICIENT, False, False
    return ("通過" if passed else "未通過"), passed, True


def evaluate_conditions(
    *,
    scan: ScanRecord,
    delta: float | None,
    spread_rate: float | None,
    annual_return: float | None,
    open_interest: int | None,
) -> ConditionEvaluation:
    delta_result = _condition_result(
        abs(delta) if delta is not None else None,
        scan.delta_operator,
        scan.delta_threshold,
    )
    spread_result = _condition_result(
        spread_rate, scan.spread_operator, scan.spread_threshold
    )
    annual_result = _condition_result(
        annual_return,
        scan.annual_return_operator,
        scan.annual_return_threshold,
    )
    if scan.open_interest_min is None:
        open_interest_result = ("未設定", True, True)
    elif open_interest is None:
        open_interest_result = (INSUFFICIENT, False, False)
    else:
        passed = open_interest > scan.open_interest_min
        open_interest_result = ("通過" if passed else "未通過", passed, True)

    results = (delta_result, spread_result, annual_result, open_interest_result)
    if not scan.has_active_conditions:
        matched: bool | None = False
    elif not all(result[2] for result in results):
        matched = None
    else:
        matched = all(result[1] for result in results)
    return ConditionEvaluation(
        has_active_conditions=scan.has_active_conditions,
        matched=matched,
        delta_result=delta_result[0],
        spread_result=spread_result[0],
        annual_return_result=annual_result[0],
        open_interest_result=open_interest_result[0],
    )


def evaluate_contract_alert(
    *,
    evaluation: ConditionEvaluation,
    baseline_established: bool,
    previous_armed: bool | None,
    previous_nonmatches: int,
    email_enabled: bool,
) -> ContractAlertDecision:
    if not evaluation.has_active_conditions:
        return ContractAlertDecision(NO_CONDITIONS, True, 0, False)
    if evaluation.matched is None:
        return ContractAlertDecision(
            INSUFFICIENT,
            True if previous_armed is None else previous_armed,
            max(0, previous_nonmatches),
            False,
        )
    if not baseline_established:
        return ContractAlertDecision(
            "初次基準",
            not evaluation.matched,
            0 if evaluation.matched else 1,
            False,
        )
    if evaluation.matched:
        armed = True if previous_armed is None else previous_armed
        return ContractAlertDecision(
            "新符合" if armed else "持續符合",
            False,
            0,
            bool(armed and email_enabled),
        )
    count = max(0, previous_nonmatches) + 1
    armed = bool(previous_armed) or count >= 2
    return ContractAlertDecision(NOT_MATCHED, armed, count, False)
