from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
)


def main():
    incident = Incident(
        service="payment-service",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log="Database connection refused on port 5432",
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
            "action": "Investigate PostgreSQL availability.",
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

    print("\nValidation:")
    print("Incident:", type(incident).__name__)
    print("Analysis:", type(analysis).__name__)
    print("Confidence:", analysis.confidence)
    print("Requires approval:", analysis.remediation.requires_approval)


if __name__ == "__main__":
    main()
