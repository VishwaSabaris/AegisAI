import json

from backend.app.models.incident import Incident
from backend.app.models.remediation import RemediationApproval
from backend.app.services.orchestrator import IncidentOrchestrator


SERVICE = "payment-service"
NAMESPACE = "aegis-demo"


def create_incident() -> Incident:
    return Incident(
        service=SERVICE,
        namespace=NAMESPACE,
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log="Database connection refused on port 5432",
    )


def test_rejected_approval() -> None:
    print("\n" + "=" * 60)
    print("TEST 1 - REJECTED APPROVAL")
    print("=" * 60)

    orchestrator = IncidentOrchestrator()
    incident = create_incident()

    workflow = orchestrator.process_incident(incident)

    assert workflow.approval_required is True

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "AWAITING_APPROVAL"

    approval = RemediationApproval(
        approved=False,
        approved_by="test-user",
        comment="Do not modify the deployment.",
    )

    result = orchestrator.approve_and_execute(
        incident=incident,
        approval=approval,
    )

    print("\nResult:")
    print(json.dumps(result, indent=2))

    assert result["success"] is False
    assert result["status"] == "REJECTED"
    assert result["remediation_executed"] is False
    assert result["recovery_status"] is None

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "REJECTED"

    history = (
        orchestrator.remediation_agent.registry
        .get_execution_history()
    )

    assert len(history) == 0

    print("\nRejected approval correctly blocked remediation.")
    print("Kubernetes remediation tool was never executed.")


def test_approved_but_unhealthy_recovery() -> None:
    print("\n" + "=" * 60)
    print("TEST 2 - APPROVED REMEDIATION")
    print("=" * 60)

    orchestrator = IncidentOrchestrator()
    incident = create_incident()

    workflow = orchestrator.process_incident(incident)

    assert workflow.approval_required is True

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "AWAITING_APPROVAL"

    approval = RemediationApproval(
        approved=True,
        approved_by="test-user",
        comment="Approved restart for controlled recovery test.",
    )

    result = orchestrator.approve_and_execute(
        incident=incident,
        approval=approval,
    )

    print("\nResult:")
    print(json.dumps(result, indent=2))

    assert result["remediation_executed"] is True
    assert result["status"] == "NOT_RECOVERED"
    assert result["recovery_status"] == "NOT_RECOVERED"

    assert result["execution"]["success"] is True
    assert result["verification"]["success"] is True

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    assert lifecycle.state == "FAILED"

    history = (
        orchestrator.remediation_agent.registry
        .get_execution_history()
    )

    assert len(history) == 2

    assert history[0].tool_name == "restart_deployment"
    assert history[0].success is True

    assert history[1].tool_name == "verify_deployment"
    assert history[1].success is True

    print("\nApproved remediation was executed.")
    print(
        "Recovery verification correctly detected "
        "the unhealthy application."
    )


def main() -> None:
    test_rejected_approval()
    test_approved_but_unhealthy_recovery()

    print("\n" + "=" * 60)
    print("MILESTONE 5B/5D APPROVAL GATE TEST")
    print("=" * 60)

    print(
        "\nRejected path:"
        "\n  Incident: PROCESSED"
        "\n  Lifecycle: AWAITING_APPROVAL -> REJECTED"
        "\n  Remediation: BLOCKED"
        "\n  Kubernetes write: NONE"
    )

    print(
        "\nApproved path:"
        "\n  Incident: PROCESSED"
        "\n  Lifecycle: AWAITING_APPROVAL -> APPROVED"
        "\n  Remediation: EXECUTED"
        "\n  Recovery: NOT_RECOVERED"
        "\n  Final lifecycle: FAILED"
    )

    print("\nAll approval-gate assertions passed.")


if __name__ == "__main__":
    main()
