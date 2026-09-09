from unittest.mock import MagicMock

from backend.app.core.database import SessionLocal
from backend.app.db.models import IncidentRecord
from backend.app.models.incident import Incident
from backend.app.models.remediation import RemediationApproval
from backend.app.services.orchestrator import IncidentOrchestrator


def create_record(
    incident_id: str,
    lifecycle_state: str,
    previous_state: str,
    lifecycle_message: str,
    approval_status: str,
    recovery_status: str | None,
) -> None:
    db = SessionLocal()

    try:
        existing = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident_id == incident_id
            )
            .first()
        )

        if existing is not None:
            db.delete(existing)
            db.commit()

        record = IncidentRecord(
            incident_id=incident_id,
            service="payment-service",
            namespace="aegis-demo",
            environment="production",
            status="CrashLoopBackOff",
            recent_log=(
                "ERROR Database connection refused "
                "on port 5432"
            ),
            lifecycle_state=lifecycle_state,
            previous_lifecycle_state=previous_state,
            lifecycle_message=lifecycle_message,
            severity="high",
            root_cause=(
                "The payment-service cannot connect to "
                "the PostgreSQL database."
            ),
            confidence=0.94,
            evidence=[
                "Pod payment-service-abc123 is not ready.",
                "Container is in CrashLoopBackOff state.",
                "Database connection refused on port 5432.",
            ],
            next_checks=[
                "Verify PostgreSQL service availability.",
                "Check PostgreSQL endpoint configuration.",
            ],
            remediation_action="restart_deployment",
            remediation_risk="medium",
            requires_approval=True,
            approval_status=approval_status,
            recovery_status=recovery_status,
        )

        db.add(record)
        db.commit()

    finally:
        db.close()


def delete_record(incident_id: str) -> None:
    db = SessionLocal()

    try:
        record = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident_id == incident_id
            )
            .first()
        )

        if record is not None:
            db.delete(record)
            db.commit()

    finally:
        db.close()


def test_orchestrator_rehydrates_pending_approval_without_llm(
    monkeypatch,
):
    """
    Verify that a persisted AWAITING_APPROVAL incident is
    restored into a fresh orchestrator process without
    invoking the Investigation Agent / LLM again.

    Also verify that persisted evidence and next_checks are
    restored into the reconstructed IncidentAnalysis.
    """

    incident_id = "rehydration-test-incident"

    create_record(
        incident_id=incident_id,
        lifecycle_state="AWAITING_APPROVAL",
        previous_state="ANALYZED",
        lifecycle_message=(
            "Remediation requires explicit human approval."
        ),
        approval_status="PENDING",
        recovery_status=None,
    )

    llm_called = False

    def fail_if_llm_called(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        raise AssertionError(
            "InvestigationAgent.investigate() should not "
            "be called during orchestrator rehydration."
        )

    monkeypatch.setattr(
        "backend.app.services.orchestrator.InvestigationAgent.investigate",
        fail_if_llm_called,
    )

    try:
        orchestrator = IncidentOrchestrator()

        lifecycle = orchestrator.get_lifecycle(
            incident_id
        )

        assert lifecycle.state == "AWAITING_APPROVAL"
        assert lifecycle.previous_state == "ANALYZED"
        assert (
            lifecycle.message
            == "Remediation requires explicit human approval."
        )

        workflow = orchestrator._workflows.get(
            incident_id
        )

        assert workflow is not None
        assert workflow.stage == "approval_required"
        assert workflow.incident == "payment-service"

        assert workflow.analysis.severity == "high"

        assert (
            workflow.analysis.root_cause
            == (
                "The payment-service cannot connect to "
                "the PostgreSQL database."
            )
        )

        assert workflow.analysis.confidence == 0.94

        assert workflow.analysis.evidence == [
            "Pod payment-service-abc123 is not ready.",
            "Container is in CrashLoopBackOff state.",
            "Database connection refused on port 5432.",
        ]

        assert workflow.analysis.next_checks == [
            "Verify PostgreSQL service availability.",
            "Check PostgreSQL endpoint configuration.",
        ]

        assert (
            workflow.analysis.remediation.action
            == "restart_deployment"
        )

        assert (
            workflow.analysis.remediation.risk
            == "medium"
        )

        assert (
            workflow.analysis.remediation.requires_approval
            is True
        )

        assert workflow.approval_required is True
        assert workflow.remediation_executed is False
        assert workflow.recovery_status is None

        remediation_request = (
            orchestrator._remediation_requests.get(
                incident_id
            )
        )

        assert remediation_request is not None

        assert (
            remediation_request.action
            == "restart_deployment"
        )

        assert (
            remediation_request.service
            == "payment-service"
        )

        assert (
            remediation_request.namespace
            == "aegis-demo"
        )

        assert (
            remediation_request.reason
            == (
                "The payment-service cannot connect to "
                "the PostgreSQL database."
            )
        )

        assert workflow.risk_decision is not None

        assert (
            workflow.risk_decision.action
            == "restart_deployment"
        )

        assert (
            workflow.risk_decision.risk
            == "medium"
        )

        assert (
            workflow.risk_decision.requires_approval
            is True
        )

        assert llm_called is False

    finally:
        delete_record(incident_id)


def test_orchestrator_rehydrates_rejected_incident_as_completed(
    monkeypatch,
):
    """
    Verify that a rejected remediation is restored as a
    completed workflow and is no longer marked as awaiting
    approval.
    """

    incident_id = "rehydration-rejected-incident"

    create_record(
        incident_id=incident_id,
        lifecycle_state="REJECTED",
        previous_state="AWAITING_APPROVAL",
        lifecycle_message=(
            "Human approval rejected the remediation."
        ),
        approval_status="REJECTED",
        recovery_status=None,
    )

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError(
            "LLM should not be called during rehydration."
        )

    monkeypatch.setattr(
        "backend.app.services.orchestrator.InvestigationAgent.investigate",
        fail_if_llm_called,
    )

    try:
        orchestrator = IncidentOrchestrator()

        lifecycle = orchestrator.get_lifecycle(
            incident_id
        )

        assert lifecycle.state == "REJECTED"

        workflow = orchestrator._workflows.get(
            incident_id
        )

        assert workflow is not None
        assert workflow.stage == "completed"
        assert workflow.approval_required is False
        assert workflow.remediation_executed is False
        assert workflow.recovery_status is None

        assert workflow.analysis.evidence == [
            "Pod payment-service-abc123 is not ready.",
            "Container is in CrashLoopBackOff state.",
            "Database connection refused on port 5432.",
        ]

        assert workflow.analysis.next_checks == [
            "Verify PostgreSQL service availability.",
            "Check PostgreSQL endpoint configuration.",
        ]

    finally:
        delete_record(incident_id)


def test_orchestrator_rehydrates_failed_remediation_as_completed(
    monkeypatch,
):
    """
    Verify that a remediation which was approved and executed
    but failed recovery is restored as a completed workflow.
    """

    incident_id = "rehydration-failed-incident"

    create_record(
        incident_id=incident_id,
        lifecycle_state="FAILED",
        previous_state="VERIFYING",
        lifecycle_message=(
            "Remediation completed but service did not recover."
        ),
        approval_status="APPROVED",
        recovery_status="NOT_RECOVERED",
    )

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError(
            "LLM should not be called during rehydration."
        )

    monkeypatch.setattr(
        "backend.app.services.orchestrator.InvestigationAgent.investigate",
        fail_if_llm_called,
    )

    try:
        orchestrator = IncidentOrchestrator()

        lifecycle = orchestrator.get_lifecycle(
            incident_id
        )

        assert lifecycle.state == "FAILED"

        workflow = orchestrator._workflows.get(
            incident_id
        )

        assert workflow is not None
        assert workflow.stage == "completed"
        assert workflow.approval_required is False
        assert workflow.remediation_executed is True
        assert workflow.recovery_status == "NOT_RECOVERED"

        assert workflow.risk_decision is not None

        assert (
            workflow.risk_decision.requires_approval
            is True
        )

        assert workflow.analysis.evidence == [
            "Pod payment-service-abc123 is not ready.",
            "Container is in CrashLoopBackOff state.",
            "Database connection refused on port 5432.",
        ]

        assert workflow.analysis.next_checks == [
            "Verify PostgreSQL service availability.",
            "Check PostgreSQL endpoint configuration.",
        ]

    finally:
        delete_record(incident_id)


def test_rehydrated_pending_approval_can_execute_without_llm(
    monkeypatch,
):
    """
    Verify that a fresh orchestrator can rehydrate an
    AWAITING_APPROVAL incident and execute its approved
    remediation without running investigation/LLM again.
    """

    incident_id = "rehydration-approval-execution"

    create_record(
        incident_id=incident_id,
        lifecycle_state="AWAITING_APPROVAL",
        previous_state="ANALYZED",
        lifecycle_message=(
            "Remediation requires explicit human approval."
        ),
        approval_status="PENDING",
        recovery_status=None,
    )

    llm_called = False

    def fail_if_llm_called(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        raise AssertionError(
            "LLM should not be called after rehydration "
            "when processing approval."
        )

    monkeypatch.setattr(
        "backend.app.services.orchestrator.InvestigationAgent.investigate",
        fail_if_llm_called,
    )

    try:
        orchestrator = IncidentOrchestrator()

        incident = Incident(
            incident_id=incident_id,
            service="payment-service",
            namespace="aegis-demo",
            environment="production",
            status="CrashLoopBackOff",
            recent_log=(
                "ERROR Database connection refused "
                "on port 5432"
            ),
        )

        # Replace the real remediation execution with a
        # deterministic mock. This test is specifically
        # verifying rehydration + approval execution, not
        # Kubernetes behavior.
        mock_execution = MagicMock(
            return_value={
                "success": True,
                "action": "restart_deployment",
                "service": "payment-service",
                "namespace": "aegis-demo",
            }
        )

        monkeypatch.setattr(
            orchestrator.remediation_agent,
            "execute",
            mock_execution,
        )

        # Replace verification with a deterministic recovered
        # result so the test does not depend on live Kubernetes.
        mock_verification = MagicMock(
            return_value={
                "success": True,
                "data": {
                    "recovery_status": "RECOVERED",
                },
            }
        )

        monkeypatch.setattr(
            orchestrator.remediation_agent,
            "verify",
            mock_verification,
        )

        approval = RemediationApproval(
            approved=True,
            approved_by="rehydration-test",
            comment=(
                "Approve remediation after "
                "orchestrator restart."
            ),
        )

        result = orchestrator.approve_and_execute(
            incident=incident,
            approval=approval,
        )

        assert result["success"] is True
        assert result["status"] == "RECOVERED"
        assert result["incident_id"] == incident_id
        assert result["remediation_executed"] is True
        assert result["recovery_status"] == "RECOVERED"

        assert (
            result["approval"]["approved"]
            is True
        )

        mock_execution.assert_called_once()

        mock_verification.assert_called_once_with(
            service="payment-service",
            namespace="aegis-demo",
        )

        assert llm_called is False

        lifecycle = orchestrator.get_lifecycle(
            incident_id
        )

        assert lifecycle.state == "RECOVERED"

        workflow = orchestrator.get_workflow(
            incident_id
        )

        assert workflow.stage == "completed"
        assert workflow.approval_required is False
        assert workflow.remediation_executed is True
        assert workflow.recovery_status == "RECOVERED"

    finally:
        delete_record(incident_id)
