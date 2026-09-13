import json

import pytest

from backend.app.models.incident import Incident
from backend.app.services.orchestrator import IncidentOrchestrator


def create_incident() -> Incident:
    return Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log="Database connection refused on port 5432",
    )

@pytest.mark.e2e
def test_incident_orchestrator() -> None:
    print("=" * 60)
    print("AegisAI - Incident Orchestrator Test")
    print("=" * 60)

    incident = create_incident()

    print("\nIncident:")
    print(
        json.dumps(
            incident.model_dump(),
            indent=2,
        )
    )

    orchestrator = IncidentOrchestrator()

    print("\nProcessing incident...")

    result = orchestrator.process_incident(incident)

    print("\nWorkflow result:")
    print("-" * 60)
    print(
        json.dumps(
            result.model_dump(),
            indent=2,
        )
    )
    print("-" * 60)

    # Validate incident identification
    assert result.incident == "payment-service"

    # Validate workflow stage
    assert result.stage == "approval_required"

    # Validate severity
    assert result.analysis.severity in {
        "low",
        "medium",
        "high",
        "critical",
    }

    # Validate root cause
    assert result.analysis.root_cause

    # Validate confidence score
    assert (
        0.0
        <= result.analysis.confidence
        <= 1.0
    )

    # Validate risk decision
    assert result.risk_decision is not None

    assert (
        result.risk_decision.action
        == result.analysis.remediation.action
    )

    assert (
        result.risk_decision.requires_approval
        is True
    )

    # Validate approval gate
    assert result.approval_required is True

    # Remediation must not execute before approval
    assert result.remediation_executed is False

    # Recovery should not have started
    assert result.recovery_status is None

    # Validate lifecycle
    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "AWAITING_APPROVAL"

    assert lifecycle.previous_state == "ANALYZED"

    # Print validation results
    print("\nWorkflow validation:")
    print("  Investigation: SUCCESS")
    print("  Gemma analysis: SUCCESS")
    print("  Risk evaluation: SUCCESS")
    print("  Lifecycle integration: SUCCESS")
    print("  Approval required: YES")
    print("  Remediation executed: NO")

    print("\nHuman approval boundary preserved.")
    print("\nAll assertions passed.")


if __name__ == "__main__":
    test_incident_orchestrator()
