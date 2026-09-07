from backend.app.core.database import SessionLocal
from backend.app.db.models import IncidentRecord


def test_persistence() -> None:
    db = SessionLocal()

    try:
        incident = IncidentRecord(
            incident_id="persistence-test-001",
            service="payment-service",
            namespace="aegis-demo",
            environment="Kubernetes",
            status="CrashLoopBackOff",
            recent_log="Database connection refused on port 5432",
            lifecycle_state="DETECTED",
            lifecycle_message="Incident detected.",
        )

        db.add(incident)
        db.commit()

        print(f"Inserted incident: {incident.incident_id}")

        stored_incident = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident_id == "persistence-test-001"
            )
            .first()
        )

        if stored_incident is None:
            raise RuntimeError("Incident was not found after insertion.")

        print(f"Read incident: {stored_incident.incident_id}")
        print(f"Service: {stored_incident.service}")
        print(f"Lifecycle: {stored_incident.lifecycle_state}")

    finally:
        db.close()


if __name__ == "__main__":
    test_persistence()
