from app.engine.controller import decide
from app.engine.types import ConflictBand, DecisionAction, MachineAction


def test_medium_confidence_requests_data_and_holds_actuation():
    action, machine_action, _, recommended = decide(
        0.5,
        73.0,
        ConflictBand.HIGH,
        [],
    )

    assert action == DecisionAction.REQUEST_DATA
    assert machine_action == MachineAction.HOLD
    assert "Request another sample" in recommended


def test_low_confidence_defers_and_recommends_human_verification():
    action, machine_action, _, recommended = decide(
        0.49,
        73.0,
        ConflictBand.HIGH,
        [],
    )

    assert action == DecisionAction.DEFER
    assert machine_action == MachineAction.HOLD
    assert "human verification" in recommended
