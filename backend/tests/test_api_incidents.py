from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.api.incidents import _orchestrator
from backend.app.main import app
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
        headers=get_auth_headers(),
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

    fake_repository.get_paginated.return_value = (
        [],
        0,
        0,
    )

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total"] == 0
    assert data["total_pages"] == 0
    assert data["filters"] == {
        "service": None,
        "namespace": None,
        "lifecycle_state": None,
    }
    assert data["incidents"] == []

    fake_repository.get_paginated.assert_called_once_with(
        page=1,
        page_size=20,
        service=None,
        namespace=None,
        lifecycle_state=None,
    )


def test_list_incidents_with_pagination_and_filters():
    fake_repository = MagicMock()

    fake_record = MagicMock()
    fake_record.incident_id = "incident-123"
    fake_record.service = "payment-service"
    fake_record.namespace = "aegis-demo"
    fake_record.environment = "kubernetes"
    fake_record.status = "CrashLoopBackOff"
    fake_record.lifecycle_state = "AWAITING_APPROVAL"
    fake_record.severity = "critical"
    fake_record.root_cause = "Database connection failure"
    fake_record.confidence = 0.95
    fake_record.remediation_action = "restart_deployment"
    fake_record.remediation_risk = "medium"
    fake_record.requires_approval = True
    fake_record.approval_status = "PENDING"
    fake_record.recovery_status = None

    fake_record.created_at = datetime(
        2026,
        9,
        10,
        10,
        0,
        0,
        tzinfo=timezone.utc,
    )

    fake_record.updated_at = datetime(
        2026,
        9,
        10,
        10,
        5,
        0,
        tzinfo=timezone.utc,
    )

    fake_repository.get_paginated.return_value = (
        [fake_record],
        41,
        3,
    )

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents"
            "?page=2"
            "&page_size=20"
            "&service=payment-service"
            "&namespace=aegis-demo"
            "&lifecycle_state=AWAITING_APPROVAL",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["page"] == 2
    assert data["page_size"] == 20
    assert data["total"] == 41
    assert data["total_pages"] == 3

    assert data["filters"] == {
        "service": "payment-service",
        "namespace": "aegis-demo",
        "lifecycle_state": "AWAITING_APPROVAL",
    }

    assert len(data["incidents"]) == 1

    incident = data["incidents"][0]

    assert incident["incident_id"] == "incident-123"
    assert incident["service"] == "payment-service"
    assert incident["namespace"] == "aegis-demo"
    assert incident["environment"] == "kubernetes"
    assert incident["status"] == "CrashLoopBackOff"
    assert incident["lifecycle_state"] == "AWAITING_APPROVAL"
    assert incident["severity"] == "critical"
    assert incident["root_cause"] == "Database connection failure"
    assert incident["confidence"] == 0.95
    assert incident["remediation_action"] == "restart_deployment"
    assert incident["remediation_risk"] == "medium"
    assert incident["requires_approval"] is True
    assert incident["approval_status"] == "PENDING"
    assert incident["recovery_status"] is None

    assert (
        incident["created_at"]
        == "2026-09-10T10:00:00+00:00"
    )

    assert (
        incident["updated_at"]
        == "2026-09-10T10:05:00+00:00"
    )

    fake_repository.get_paginated.assert_called_once_with(
        page=2,
        page_size=20,
        service="payment-service",
        namespace="aegis-demo",
        lifecycle_state="AWAITING_APPROVAL",
    )


def test_dashboard_summary():
    fake_repository = MagicMock()

    fake_repository.get_dashboard_summary.return_value = {
        "total_incidents": 400,
        "active_incidents": 140,
        "recovered_incidents": 0,
        "failed_incidents": 134,
        "pending_approval": 130,
        "severity_distribution": {
            "high": 359,
            "critical": 25,
        },
        "lifecycle_distribution": {
            "AWAITING_APPROVAL": 130,
            "DETECTED": 6,
            "FAILED": 134,
            "REJECTED": 126,
            "INVESTIGATING": 4,
        },
    }

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents/dashboard/summary",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True

    assert data["summary"] == {
        "total_incidents": 400,
        "active_incidents": 140,
        "recovered_incidents": 0,
        "failed_incidents": 134,
        "pending_approval": 130,
        "severity_distribution": {
            "high": 359,
            "critical": 25,
        },
        "lifecycle_distribution": {
            "AWAITING_APPROVAL": 130,
            "DETECTED": 6,
            "FAILED": 134,
            "REJECTED": 126,
            "INVESTIGATING": 4,
        },
    }

    fake_repository.get_dashboard_summary.assert_called_once_with()


def test_dashboard_summary_route_is_not_treated_as_incident_id():
    fake_repository = MagicMock()

    fake_repository.get_dashboard_summary.return_value = {
        "total_incidents": 0,
        "active_incidents": 0,
        "recovered_incidents": 0,
        "failed_incidents": 0,
        "pending_approval": 0,
        "severity_distribution": {},
        "lifecycle_distribution": {},
    }

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents/dashboard/summary",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_list_incidents_invalid_page():
    response = client.get(
        "/incidents?page=0",
        headers=get_auth_headers(),
    )

    assert response.status_code == 422


def test_list_incidents_invalid_page_size():
    response = client.get(
        "/incidents?page_size=101",
        headers=get_auth_headers(),
    )

    assert response.status_code == 422


def test_get_incident_not_found():
    fake_repository = MagicMock()
    fake_repository.get_by_incident_id.return_value = None

    with patch(
        "backend.app.api.incidents.IncidentRepository",
        return_value=fake_repository,
    ):
        response = client.get(
            "/incidents/non-existent-id",
            headers=get_auth_headers(),
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
            headers=get_auth_headers(),
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
            headers=get_auth_headers(),
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
            headers=get_auth_headers(),
            json={
                "approved": True,
                "approved_by": "test-user",
                "comment": "Approved",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_result

def test_approval_uses_authenticated_user_as_approver():
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
        ) as mock_approve_and_execute,
    ):
        response = client.post(
            "/incidents/test-incident/approval",
            headers=get_auth_headers(),
            json={
                "approved": True,
                "approved_by": "attacker",
                "comment": "Approved",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_result

    approval_argument = (
        mock_approve_and_execute.call_args.kwargs["approval"]
    )

    assert approval_argument.approved is True
    assert approval_argument.approved_by == "testadmin"
    assert approval_argument.approved_by != "attacker"
    assert approval_argument.comment == "Approved"

def test_create_incident_validation():
    response = client.post(
        "/incidents",
        headers=get_auth_headers(),
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
            headers=get_auth_headers(),
            json={
                "approved": False,
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_result
