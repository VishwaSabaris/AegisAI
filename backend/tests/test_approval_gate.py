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


def test_approved_remediation_recovery() -> None:
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

    assert result["execution"]["success"] is True
    assert result["execution"]["action"] == "restart_deployment"

    assert result["verification"]["success"] is True

    recovery_status = result["recovery_status"]

    assert recovery_status in {
        "RECOVERED",
        "NOT_RECOVERED",
    }

    lifecycle = orchestrator.get_lifecycle(
        incident.incident_id
    )

    if recovery_status == "RECOVERED":
        assert result["status"] == "RECOVERED"
        assert lifecycle.state == "RECOVERED"

        final_workflow = orchestrator._workflows[
            incident.incident_id
        ]

        assert final_workflow.stage == "completed"
        assert final_workflow.approval_required is False
        assert final_workflow.remediation_executed is True
        assert final_workflow.recovery_status == "RECOVERED"

        print("\nApproved remediation successfully recovered the service.")

    else:
        assert result["status"] == "NOT_RECOVERED"
        assert lifecycle.state == "FAILED"

        final_workflow = orchestrator._workflows[
            incident.incident_id
        ]

        assert final_workflow.stage == "completed"
        assert final_workflow.approval_required is False
        assert final_workflow.remediation_executed is True
        assert final_workflow.recovery_status == "NOT_RECOVERED"

        print(
            "\nApproved remediation executed, "
            "but recovery verification detected that "
            "the service was still unhealthy."
        )

    history = (
        orchestrator.remediation_agent.registry
        .get_execution_history()
    )

    assert len(history) == 2

    assert history[0].tool_name == "restart_deployment"
    assert history[0].success is True

    assert history[1].tool_name == "verify_deployment"
    assert history[1].success is True

    print("\nApproval gate and remediation execution assertions passed.")


def main() -> None:
    test_rejected_approval()
    test_approved_remediation_recovery()

    print("\n" + "=" * 60)
    print("APPROVAL GATE TEST")
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
        "\n  Recovery: VERIFIED"
        "\n  Final lifecycle: RECOVERED or FAILED"
    )

    print("\nAll approval-gate assertions passed.")


if __name__ == "__main__":
    main()
