import pytest

from backend.app.models.dashboard import (
    DashboardSummary,
    DashboardSummaryResponse,
)
from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
)


def test_dashboard_summary_model():
    summary = DashboardSummary(
        total_incidents=400,
        active_incidents=140,
        recovered_incidents=0,
        failed_incidents=134,
        pending_approval=130,
        severity_distribution={
            "high": 359,
            "critical": 25,
        },
        lifecycle_distribution={
            "AWAITING_APPROVAL": 130,
            "DETECTED": 6,
            "FAILED": 134,
            "REJECTED": 126,
            "INVESTIGATING": 4,
        },
    )

    assert summary.total_incidents == 400
    assert summary.active_incidents == 140
    assert summary.recovered_incidents == 0
    assert summary.failed_incidents == 134
    assert summary.pending_approval == 130

    assert summary.severity_distribution["high"] == 359
    assert summary.severity_distribution["critical"] == 25

    assert (
        summary.lifecycle_distribution["FAILED"]
        == 134
    )


def test_dashboard_summary_model_rejects_negative_counts():
    with pytest.raises(ValueError):
        DashboardSummary(
            total_incidents=-1,
            active_incidents=0,
            recovered_incidents=0,
            failed_incidents=0,
            pending_approval=0,
        )


def test_dashboard_summary_response_model():
    response = DashboardSummaryResponse(
        success=True,
        summary={
            "total_incidents": 10,
            "active_incidents": 4,
            "recovered_incidents": 3,
            "failed_incidents": 2,
            "pending_approval": 1,
            "severity_distribution": {
                "high": 6,
                "critical": 4,
            },
            "lifecycle_distribution": {
                "AWAITING_APPROVAL": 1,
                "INVESTIGATING": 2,
                "RECOVERED": 3,
                "FAILED": 2,
                "REJECTED": 2,
            },
        },
    )

    assert response.success is True
    assert response.summary.total_incidents == 10
    assert (
        response.summary.severity_distribution[
            "critical"
        ]
        == 4
    )


def main():
    incident = Incident(
        service="payment-service",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused "
            "on port 5432"
        ),
    )

    analysis = IncidentAnalysis(
        severity="high",
        root_cause="PostgreSQL is unreachable.",
        confidence=0.85,
        evidence=[
            "Database connection refused on port 5432",
            "payment-service is in CrashLoopBackOff",
        ],
        next_checks=[
            "Check PostgreSQL pod status.",
            "Check Kubernetes service endpoints.",
        ],
        remediation={
            "action": "restart_deployment",
            "risk": "medium",
            "requires_approval": True,
        },
    )

    print("=" * 60)
    print("AegisAI - Pydantic Model Test")
    print("=" * 60)

    print("\nIncident:")
    print(incident.model_dump_json(indent=2))

    print("\nAnalysis:")
    print(analysis.model_dump_json(indent=2))

    print("\nDashboard Summary:")
    dashboard_summary = DashboardSummary(
        total_incidents=400,
        active_incidents=140,
        recovered_incidents=0,
        failed_incidents=134,
        pending_approval=130,
        severity_distribution={
            "high": 359,
            "critical": 25,
        },
        lifecycle_distribution={
            "AWAITING_APPROVAL": 130,
            "DETECTED": 6,
            "FAILED": 134,
            "REJECTED": 126,
            "INVESTIGATING": 4,
        },
    )

    dashboard_response = DashboardSummaryResponse(
        success=True,
        summary=dashboard_summary,
    )

    print(
        dashboard_response.model_dump_json(
            indent=2
        )
    )

    print("\nValidation:")
    print("Incident:", type(incident).__name__)
    print("Analysis:", type(analysis).__name__)
    print(
        "Dashboard Summary:",
        type(dashboard_summary).__name__,
    )
    print(
        "Dashboard Response:",
        type(dashboard_response).__name__,
    )
    print("Confidence:", analysis.confidence)
    print(
        "Requires approval:",
        analysis.remediation.requires_approval,
    )


if __name__ == "__main__":
    main()
