from backend.app.core.database import SessionLocal
from backend.app.db.models import IncidentRecord
from backend.app.models.incident import Incident
from backend.app.services.orchestrator import IncidentOrchestrator


def test_orchestrator_rehydrates_pending_approval_without_llm(
    monkeypatch,
):
    """
    Verify that a persisted AWAITING_APPROVAL incident is
    restored into a fresh orchestrator process without
    invoking the Investigation Agent / LLM again.
    """

    incident_id = "rehydration-test-incident"

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
            lifecycle_state="AWAITING_APPROVAL",
            previous_lifecycle_state="ANALYZED",
            lifecycle_message=(
                "Remediation requires explicit human approval."
            ),
            severity="high",
            root_cause=(
                "The payment-service cannot connect to "
                "the PostgreSQL database."
            ),
            confidence=0.94,
            remediation_action="restart_deployment",
            remediation_risk="medium",
            requires_approval=True,
            approval_status="PENDING",
            recovery_status=None,
        )

        db.add(record)
        db.commit()

    finally:
        db.close()

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
        assert (
            lifecycle.previous_state
            == "ANALYZED"
        )
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

        assert (
            workflow.analysis.severity
            == "high"
        )

        assert (
            workflow.analysis.root_cause
            == (
                "The payment-service cannot connect to "
                "the PostgreSQL database."
            )
        )

        assert (
            workflow.analysis.confidence
            == 0.94
        )

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

        assert (
            workflow.risk_decision is not None
        )

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
        db = SessionLocal()

        try:
            record = (
                db.query(IncidentRecord)
                .filter(
                    IncidentRecord.incident_id
                    == incident_id
                )
                .first()
            )

            if record is not None:
                db.delete(record)
                db.commit()

        finally:
            db.close()
