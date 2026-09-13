import uuid
import pytest

from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)
from backend.app.security.jwt import create_access_token


client = TestClient(app)


def get_auth_headers() -> dict[str, str]:
    token = create_access_token(
        subject="1",
        role="admin",
    )

    return {
        "Authorization": f"Bearer {token}",
    }

@pytest.mark.e2e
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
            -> rollout verification
            -> stability verification
            -> RECOVERED

    The test uses a unique incident payload and removes the
    persisted database record after completion.
    """

    incident_id = None
    db = SessionLocal()
    repository = IncidentRepository(db)

    try:
        response = client.post(
            "/incidents",
            headers=get_auth_headers(),
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
            f"/incidents/{incident_id}",
            headers=get_auth_headers(),
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
            headers=get_auth_headers(),
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

        assert approval_data["success"] is True
        assert approval_data["status"] == "RECOVERED"
        assert approval_data["remediation_executed"] is True
        assert approval_data["recovery_status"] == (
            "RECOVERED"
        )

        execution = approval_data["execution"]

        assert execution["success"] is True
        assert execution["service"] == "payment-service"
        assert execution["namespace"] == "aegis-demo"
        assert execution["action"] == "restart_deployment"

        verification = approval_data["verification"]

        assert verification["success"] is True

        verification_data = verification["data"]

        assert verification_data["recovery_status"] == (
            "RECOVERED"
        )
        assert verification_data["rollout_complete"] is True
        assert verification_data["desired_replicas"] == 1
        assert verification_data["updated_replicas"] == 1
        assert verification_data["available_replicas"] == 1
        assert verification_data["ready_replicas"] == 1

        stability = verification_data["stability"]

        assert stability["stable"] is True
        assert stability["observed_seconds"] >= (
            stability["required_seconds"]
        )

        assert (
            stability["rollout_wait_seconds"] >= 0
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
            "RECOVERED"
        )

        assert persisted_after.lifecycle_state == (
            "RECOVERED"
        )

        assert (
            persisted_after.remediation_action
            == remediation["action"]
        )

        final_response = client.get(
            f"/incidents/{incident_id}",
            headers=get_auth_headers(),
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
            == "RECOVERED"
        )
        assert final_data["recovery_status"] == (
            "RECOVERED"
        )

        print("\n" + "=" * 60)
        print("REAL E2E INCIDENT LIFECYCLE PASSED")
        print("=" * 60)
        print(f"Incident ID: {incident_id}")
        print("Analysis: completed")
        print("Approval: approved")
        print("Remediation: restart_deployment")
        print("Rollout: completed")
        print("Stability verification: passed")
        print("Recovery: RECOVERED")
        print("Persistence: verified")

    finally:
        if incident_id is not None:
            try:
                repository.delete(incident_id)
            finally:
                db.close()
        else:
            db.close()


if __name__ == "__main__":
    test_real_incident_lifecycle_end_to_end()
