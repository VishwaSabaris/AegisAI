import pytest

from backend.app.models.incident import Incident
from backend.app.models.remediation import RemediationApproval
from backend.app.services.orchestrator import IncidentOrchestrator

@pytest.mark.e2e
def test_incident_lifecycle_integration():
    incident = Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    orchestrator = IncidentOrchestrator()

    workflow = orchestrator.process_incident(
        incident
    )

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "AWAITING_APPROVAL"
    assert lifecycle.previous_state == "ANALYZED"

    assert workflow.stage == "approval_required"
    assert workflow.analysis is not None
    assert workflow.risk_decision is not None
    assert workflow.approval_required is True
    assert workflow.remediation_executed is False
    assert workflow.recovery_status is None

    print("\nLifecycle after analysis:")
    print(
        lifecycle.model_dump_json(
            indent=2
        )
    )

    print("\nWorkflow:")
    print(
        workflow.model_dump_json(
            indent=2
        )
    )

    print(
        "\n5D lifecycle integration test passed."
    )

@pytest.mark.e2e
def test_rejected_approval_is_terminal():
    incident = Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    orchestrator = IncidentOrchestrator()

    orchestrator.process_incident(
        incident
    )

    result = orchestrator.approve_and_execute(
        incident=incident,
        approval=RemediationApproval(
            approved=False,
            approved_by="test-user",
            comment="Reject for testing.",
        ),
    )

    assert result["status"] == "REJECTED"
    assert result["remediation_executed"] is False
    assert result["recovery_status"] is None

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "REJECTED"

    print("\nRejected lifecycle:")
    print(
        lifecycle.model_dump_json(
            indent=2
        )
    )

    print("\nRejected approval test passed.")

@pytest.mark.e2e
def test_approval_does_not_rerun_analysis(monkeypatch):
    incident = Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    orchestrator = IncidentOrchestrator()

    original_investigate = (
        orchestrator.investigation_agent.investigate
    )

    call_count = 0

    def counted_investigate(current_incident):
        nonlocal call_count

        call_count += 1

        return original_investigate(
            current_incident
        )

    monkeypatch.setattr(
        orchestrator.investigation_agent,
        "investigate",
        counted_investigate,
    )

    orchestrator.process_incident(
        incident
    )

    # Investigation must happen exactly once during
    # initial incident processing.
    assert call_count == 1

    result = orchestrator.approve_and_execute(
        incident=incident,
        approval=RemediationApproval(
            approved=True,
            approved_by="test-user",
            comment="Approve for testing.",
        ),
    )

    # Approval/remediation must not trigger another
    # investigation or LLM analysis.
    assert call_count == 1

    assert result["remediation_executed"] is True
    assert result["execution"]["success"] is True
    assert result["verification"]["success"] is True

    assert result["recovery_status"] in {
        "RECOVERED",
        "NOT_RECOVERED",
    }

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    if result["recovery_status"] == "RECOVERED":
        assert lifecycle.state == "RECOVERED"
    else:
        assert lifecycle.state == "FAILED"

    print(
        "\nInvestigation calls:",
        call_count,
    )

    print(
        "\nRecovery status:",
        result["recovery_status"],
    )

    print("\nFinal lifecycle:")
    print(
        lifecycle.model_dump_json(
            indent=2
        )
    )

    print(
        "\nApproval does not rerun analysis test passed."
    )
