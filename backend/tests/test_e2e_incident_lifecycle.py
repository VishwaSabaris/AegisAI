import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)


client = TestClient(app)


def test_real_incident_lifecycle_end_to_end():
    """
    Exercise the real incident workflow through the API.

    Expected scenario:

        POST /incidents
            -> investigation
            -> Gemma analysis
            -> risk evaluation
            -> PostgreSQL persistence
            -> AWAITING_APPROVAL

        POST /incidents/{incident_id}/approval
            -> approval
            -> real Kubernetes remediation
            -> verification
            -> NOT_RECOVERED for the intentionally broken service

    The test uses a unique incident payload and removes the
    persisted database record after completion.
    """

    incident_id = None
    db = SessionLocal()
    repository = IncidentRepository(db)

    try:
        response = client.post(
            "/incidents",
            json={
                "service": "payment-service",
                "namespace": "aegis-demo",
                "environment": "minikube",
                "status": "CrashLoopBackOff",
                "recent_log": (
                    "ERROR Database connection refused "
                    "on port 5432"
                ),
            },
        )

        assert response.status_code == 201

        create_data = response.json()

        assert create_data["success"] is True

        incident_id = create_data["incident_id"]

        assert incident_id
        assert create_data["service"] == "payment-service"
        assert create_data["namespace"] == "aegis-demo"

        workflow = create_data["workflow"]

        assert workflow["stage"] == "approval_required"
        assert workflow["approval_required"] is True
        assert workflow["remediation_executed"] is False
        assert workflow["recovery_status"] is None

        analysis = workflow["analysis"]

        assert analysis["severity"] in {
            "low",
            "medium",
            "high",
            "critical",
        }

        assert analysis["root_cause"]
        assert 0.0 <= analysis["confidence"] <= 1.0
        assert len(analysis["evidence"]) > 0

        remediation = analysis["remediation"]

        assert remediation["action"] in {
            "restart_deployment",
            "rollback_deployment",
            "scale_deployment",
        }

        assert remediation["risk"] in {
            "low",
            "medium",
            "high",
            "critical",
        }

        assert remediation["requires_approval"] is True

        lifecycle = create_data["lifecycle"]

        assert lifecycle["state"] == "AWAITING_APPROVAL"

        persisted = repository.get_by_incident_id(
            incident_id
        )

        assert persisted is not None
        assert persisted.incident_id == incident_id
        assert persisted.service == "payment-service"
        assert persisted.namespace == "aegis-demo"
        assert persisted.lifecycle_state == (
            "AWAITING_APPROVAL"
        )
        assert persisted.severity == analysis["severity"]
        assert persisted.root_cause == analysis["root_cause"]
        assert persisted.confidence == analysis["confidence"]
        assert persisted.evidence == analysis["evidence"]
        assert persisted.next_checks == analysis["next_checks"]
        assert (
            persisted.remediation_action
            == remediation["action"]
        )
        assert persisted.requires_approval is True

        get_response = client.get(
            f"/incidents/{incident_id}"
        )

        assert get_response.status_code == 200

        get_data = get_response.json()

        assert get_data["success"] is True
        assert (
            get_data["incident"]["incident_id"]
            == incident_id
        )
        assert (
            get_data["lifecycle"]["state"]
            == "AWAITING_APPROVAL"
        )
        assert get_data["workflow"] is not None

        approval_response = client.post(
            f"/incidents/{incident_id}/approval",
            json={
                "approved": True,
                "approved_by": "e2e-test",
                "comment": (
                    "Approve remediation for "
                    "end-to-end lifecycle test."
                ),
            },
        )

        assert approval_response.status_code == 200

        approval_data = approval_response.json()

        assert approval_data["success"] is False
        assert approval_data["status"] == "NOT_RECOVERED"
        assert approval_data["remediation_executed"] is True
        assert approval_data["recovery_status"] == (
            "NOT_RECOVERED"
        )

        # The approval endpoint uses its own database session.
        # Expire objects in this test session so SQLAlchemy
        # reloads the latest values from PostgreSQL.
        db.expire_all()

        persisted_after = (
            repository.get_by_incident_id(
                incident_id
            )
        )

        assert persisted_after is not None

        assert persisted_after.approval_status == (
            "APPROVED"
        )

        assert persisted_after.recovery_status == (
            "NOT_RECOVERED"
        )

        assert persisted_after.lifecycle_state == (
            "FAILED"
        )

        assert (
            persisted_after.remediation_action
            == remediation["action"]
        )

        final_response = client.get(
            f"/incidents/{incident_id}"
        )

        assert final_response.status_code == 200

        final_data = final_response.json()

        assert final_data["success"] is True
        assert (
            final_data["incident"]["incident_id"]
            == incident_id
        )
        assert (
            final_data["lifecycle"]["state"]
            == "FAILED"
        )
        assert final_data["recovery_status"] == (
            "NOT_RECOVERED"
        )

    finally:
        if incident_id is not None:
            try:
                repository.delete(incident_id)
            finally:
                db.close()
        else:
            db.close()
