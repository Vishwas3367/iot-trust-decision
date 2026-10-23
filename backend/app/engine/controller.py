from __future__ import annotations

from app.config import settings
from app.engine.types import ConflictBand, DecisionAction, MachineAction, TrustBreakdown


def decide(
    confidence: float,
    consensus: float | None,
    conflict_level: ConflictBand,
    trusts: list[TrustBreakdown],
) -> tuple[DecisionAction, MachineAction, str, str]:
    if consensus is None:
        return (
            DecisionAction.DEFER,
            MachineAction.HOLD,
            "No valid consensus could be formed from the current observations.",
            "Acquire additional readings or require human verification.",
        )

    intended = _machine_intent(consensus)
    low_trust_dominant = _mean_trust(trusts) < 0.42

    if confidence >= settings.execute_confidence:
        reason = _execute_reason(intended, consensus, conflict_level)
        return DecisionAction.EXECUTE, intended, reason, "Carry out the machine action."

    if confidence >= settings.request_confidence:
        reason = (
            f"Consensus is {consensus:.1f}°C toward {intended.value}, but decision confidence "
            f"is only {confidence:.0%}. Conflict is {conflict_level.value}."
        )
        if low_trust_dominant:
            reason += " Dominant evidence is only moderately trusted."
        return (
            DecisionAction.REQUEST_DATA,
            MachineAction.HOLD,
            reason,
            "Request another sample from the same sensors before acting.",
        )

    reason = (
        f"Confidence {confidence:.0%} is below the act/request band. "
        f"Conflict {conflict_level.value}; consensus {consensus:.1f}°C is not reliable enough."
    )
    return (
        DecisionAction.DEFER,
        MachineAction.HOLD,
        reason,
        "Defer the decision and require additional information or human verification.",
    )


def _machine_intent(consensus: float) -> MachineAction:
    if consensus >= settings.emergency_celsius:
        return MachineAction.SHUTDOWN
    if consensus >= settings.warning_celsius:
        return MachineAction.WARN
    return MachineAction.NORMAL


def _mean_trust(trusts: list[TrustBreakdown]) -> float:
    if not trusts:
        return 0.0
    return sum(t.trust_score for t in trusts) / len(trusts)


def _execute_reason(intended: MachineAction, consensus: float, conflict: ConflictBand) -> str:
    if intended == MachineAction.SHUTDOWN:
        return (
            f"Multiple trustworthy sources agree the machine is at {consensus:.1f}°C "
            f"(emergency threshold {settings.emergency_celsius:.0f}°C). Conflict {conflict.value} "
            "does not overturn the trusted faction."
        )
    if intended == MachineAction.WARN:
        return (
            f"Trusted consensus {consensus:.1f}°C is above the warning line "
            f"({settings.warning_celsius:.0f}°C). Execute a warning, not a blind average."
        )
    return (
        f"Trusted consensus {consensus:.1f}°C is in the normal band. "
        f"Conflict {conflict.value} was evaluated against source trust before clearing operation."
    )
