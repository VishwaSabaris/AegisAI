from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.api.incidents import _orchestrator
from backend.app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "aegisai",
    }


@patch.object(_orchestrator, "process_incident")
@patch.object(_orchestrator, "get_lifecycle")
def test_create_incident(
    mock_get_lifecycle,
    mock_process_incident,
):
    workflow = MagicMock()
    workflow.model_dump.return_value = {
        "stage": "approval_required",
        "incident": "test-incident",
        "analysis": {},
        "risk_decision": None,
        "approval_required": True,
        "remediation_executed": False,
        "recovery_status": None,
    }

    lifecycle = MagicMock()
    lifecycle.model_dump.return_value = {
        "incident_id": "test-incident",
        "state": "AWAITING_APPROVAL",
    }

    mock_process_incident.return_value = workflow
    mock_get_lifecycle.return_value = lifecycle

    response = client.post(
        "/incidents",
        json={
            "service": "payment-service",
            "namespace": "aegis-demo",
            "environment": "minikube",
            "status": "CrashLoopBackOff",
            "recent_log": "Database connection refused",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["success"] is True
    assert data["service"] == "payment-service"
    assert data["namespace"] == "aegis-demo"
    assert "incident_id" in data
    assert data["workflow"]["stage"] == "approval_required"
    assert data["lifecycle"]["state"] == "AWAITING_APPROVAL"

    mock_process_incident.assert_called_once()


def test_list_incidents():
    fake_repository = MagicMock()
    fake_repository.get_all.return_value = []

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get("/incidents")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["count"] == 0
    assert data["incidents"] == []


def test_get_incident_not_found():
    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = None

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents/non-existent-id"
        )

    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


def test_approval_incident_not_found():
    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = None

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.post(
            "/incidents/non-existent-id/approval",
            json={
                "approved": True,
                "approved_by": "test-user",
                "comment": "Approved for testing",
            },
        )

    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


def test_approval_invalid_state_returns_409():
    fake_record = MagicMock()

    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = fake_record
    fake_repository.to_incident.return_value = MagicMock()

    with (
        patch(
            "backend.app.api.incidents.IncidentRepository",
            return_value=fake_repository,
        ),
        patch.object(
            _orchestrator,
            "approve_and_execute",
            side_effect=ValueError(
                "Incident is not awaiting approval."
            ),
        ),
    ):
        response = client.post(
            "/incidents/test-incident/approval",
            json={
                "approved": True,
                "approved_by": "test-user",
            },
        )

    assert response.status_code == 409
    assert "not awaiting approval" in response.json()["detail"]


def test_approval_success():
    fake_record = MagicMock()

    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = fake_record
    fake_repository.to_incident.return_value = MagicMock()

    expected_result = {
        "success": True,
        "status": "RECOVERED",
        "remediation_executed": True,
        "recovery_status": "RECOVERED",
    }

    with (
        patch(
            "backend.app.api.incidents.IncidentRepository",
            return_value=fake_repository,
        ),
        patch.object(
            _orchestrator,
            "approve_and_execute",
            return_value=expected_result,
        ),
    ):
        response = client.post(
            "/incidents/test-incident/approval",
            json={
                "approved": True,
                "approved_by": "test-user",
                "comment": "Approved",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_result


def test_create_incident_validation():
    response = client.post(
        "/incidents",
        json={
            "service": "",
            "namespace": "aegis-demo",
            "environment": "minikube",
            "status": "CrashLoopBackOff",
            "recent_log": "Database failure",
        },
    )

    assert response.status_code == 422


def test_approval_request_accepts_optional_fields():
    fake_record = MagicMock()

    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = fake_record
    fake_repository.to_incident.return_value = MagicMock()

    expected_result = {
        "success": False,
        "status": "REJECTED",
        "remediation_executed": False,
        "recovery_status": None,
    }

    with (
        patch(
            "backend.app.api.incidents.IncidentRepository",
            return_value=fake_repository,
        ),
        patch.object(
            _orchestrator,
            "approve_and_execute",
            return_value=expected_result,
        ),
    ):
        response = client.post(
            "/incidents/test-incident/approval",
            json={
                "approved": False,
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_result
