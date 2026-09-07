import json

from backend.app.models.incident import Incident
from backend.app.services.orchestrator import (
    IncidentOrchestrator,
)


def main() -> None:
    print("=" * 60)
    print("AegisAI - Incident Orchestrator Test")
    print("=" * 60)

    incident = Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    print("\nIncident:")
    print(
        json.dumps(
            incident.model_dump(),
            indent=2,
        )
    )

    orchestrator = IncidentOrchestrator()

    print(
        "\nProcessing incident..."
    )

    result = orchestrator.process_incident(
        incident
    )

    print("\nWorkflow result:")
    print("-" * 60)
    print(
        json.dumps(
            result.model_dump(),
            indent=2,
        )
    )
    print("-" * 60)

    assert result.incident == (
        "payment-service"
    )

    assert result.stage == (
        "approval_required"
    )

    assert result.analysis.severity in {
        "low",
        "medium",
        "high",
        "critical",
    }

    assert result.analysis.root_cause

    assert (
        0.0
        <= result.analysis.confidence
        <= 1.0
    )

    assert result.risk_decision is not None

    assert (
        result.risk_decision.action
        == result.analysis.remediation.action
    )

    assert (
        result.risk_decision.requires_approval
        is True
    )

    assert (
        result.approval_required
        is True
    )

    assert (
        result.remediation_executed
        is False
    )

    assert (
        result.recovery_status
        is None
    )

    print(
        "\nWorkflow validation:"
    )

    print(
        "  Investigation: SUCCESS"
    )

    print(
        "  Gemma analysis: SUCCESS"
    )

    print(
        "  Risk evaluation: SUCCESS"
    )

    print(
        "  Approval required: YES"
    )

    print(
        "  Remediation executed: NO"
    )

    print(
        "\nHuman approval boundary preserved."
    )

    print(
        "\nAll assertions passed."
    )


if __name__ == "__main__":
    main()
