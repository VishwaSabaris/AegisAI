import json

from backend.app.services.lifecycle import (
    IncidentLifecycleManager,
)


INCIDENT_ID = "incident-test-001"
SERVICE = "payment-service"
NAMESPACE = "aegis-demo"


def test_successful_lifecycle() -> None:
    print("\n" + "=" * 60)
    print("TEST 1 - SUCCESSFUL INCIDENT LIFECYCLE")
    print("=" * 60)

    manager = IncidentLifecycleManager(
        incident_id=INCIDENT_ID,
        service=SERVICE,
        namespace=NAMESPACE,
    )

    expected_states = [
        "DETECTED",
        "INVESTIGATING",
        "ANALYZED",
        "AWAITING_APPROVAL",
        "APPROVED",
        "EXECUTING",
        "VERIFYING",
        "RECOVERED",
    ]

    assert manager.state == "DETECTED"

    print(
        f"\nInitial state: {manager.state}"
    )

    for state in expected_states[1:]:
        lifecycle = manager.transition(
            state,
            f"Transitioned to {state}.",
        )

        print(
            f"{lifecycle.previous_state}"
            f" -> "
            f"{lifecycle.state}"
        )

        assert lifecycle.state == state

    assert manager.state == "RECOVERED"

    print(
        "\nSuccessful lifecycle completed."
    )

    print(
        json.dumps(
            manager.lifecycle.model_dump(),
            indent=2,
        )
    )


def test_rejected_lifecycle() -> None:
    print("\n" + "=" * 60)
    print("TEST 2 - REJECTED INCIDENT LIFECYCLE")
    print("=" * 60)

    manager = IncidentLifecycleManager(
        incident_id="incident-test-002",
        service=SERVICE,
        namespace=NAMESPACE,
    )

    manager.transition(
        "INVESTIGATING",
        "Investigation started.",
    )

    manager.transition(
        "ANALYZED",
        "Incident analysis completed.",
    )

    manager.transition(
        "AWAITING_APPROVAL",
        "Waiting for human approval.",
    )

    manager.transition(
        "REJECTED",
        "Human rejected remediation.",
    )

    assert manager.state == "REJECTED"

    print(
        "\nLifecycle reached REJECTED."
    )

    print(
        json.dumps(
            manager.lifecycle.model_dump(),
            indent=2,
        )
    )

    assert (
        manager.allowed_transitions(
            "REJECTED"
        )
        == []
    )

    print(
        "\nRejected incidents cannot continue "
        "to remediation."
    )


def test_invalid_transitions() -> None:
    print("\n" + "=" * 60)
    print("TEST 3 - INVALID TRANSITIONS")
    print("=" * 60)

    manager = IncidentLifecycleManager(
        incident_id="incident-test-003",
        service=SERVICE,
        namespace=NAMESPACE,
    )

    invalid_transitions = [
        "RECOVERED",
        "EXECUTING",
        "APPROVED",
    ]

    for invalid_state in invalid_transitions:
        try:
            manager.transition(
                invalid_state,
                "This transition should fail.",
            )

        except ValueError as error:
            print(
                f"\nCorrectly rejected:"
                f" {manager.state}"
                f" -> "
                f"{invalid_state}"
            )

            print(
                f"Reason: {error}"
            )

        else:
            raise AssertionError(
                f"Invalid transition "
                f"{manager.state} -> "
                f"{invalid_state} "
                f"was incorrectly allowed."
            )

    assert manager.state == "DETECTED"

    print(
        "\nInvalid transitions were correctly blocked."
    )


def test_terminal_states() -> None:
    print("\n" + "=" * 60)
    print("TEST 4 - TERMINAL STATES")
    print("=" * 60)

    manager = IncidentLifecycleManager(
        incident_id="incident-test-004",
        service=SERVICE,
        namespace=NAMESPACE,
    )

    manager.transition(
        "INVESTIGATING",
        "Investigation started.",
    )

    manager.transition(
        "ANALYZED",
        "Analysis completed.",
    )

    manager.transition(
        "AWAITING_APPROVAL",
        "Waiting for approval.",
    )

    manager.transition(
        "REJECTED",
        "Human rejected remediation.",
    )

    assert (
        manager.allowed_transitions(
            "REJECTED"
        )
        == []
    )

    assert (
        manager.allowed_transitions(
            "RECOVERED"
        )
        == []
    )

    assert (
        manager.allowed_transitions(
            "FAILED"
        )
        == []
    )

    print(
        "\nREJECTED, RECOVERED and FAILED "
        "are terminal states."
    )


def main() -> None:
    test_successful_lifecycle()
    test_rejected_lifecycle()
    test_invalid_transitions()
    test_terminal_states()

    print("\n" + "=" * 60)
    print("MILESTONE 5C - LIFECYCLE TEST")
    print("=" * 60)

    print(
        "\nState machine validation: SUCCESS"
    )

    print(
        "Valid transitions: ENFORCED"
    )

    print(
        "Invalid transitions: BLOCKED"
    )

    print(
        "Terminal states: ENFORCED"
    )

    print(
        "\nAll lifecycle assertions passed."
    )


if __name__ == "__main__":
    main()
