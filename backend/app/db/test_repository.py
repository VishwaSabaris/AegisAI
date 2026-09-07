from backend.app.core.database import SessionLocal
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)


def test_repository() -> None:
    db = SessionLocal()

    try:
        repository = IncidentRepository(db)

        incident = Incident(
            incident_id="repository-test-001",
            service="payment-service",
            namespace="aegis-demo",
            environment="Kubernetes",
            status="CrashLoopBackOff",
            recent_log=(
                "Database connection refused on port 5432"
            ),
        )

        created = repository.create(incident)

        print(
            f"Created: {created.incident_id}"
        )

        stored = repository.get_by_incident_id(
            incident.incident_id
        )

        if stored is None:
            raise RuntimeError(
                "Repository could not retrieve the incident."
            )

        print(
            f"Retrieved: {stored.incident_id}"
        )
        print(
            f"Service: {stored.service}"
        )
        print(
            f"Lifecycle: {stored.lifecycle_state}"
        )

        stored.lifecycle_state = "INVESTIGATING"
        stored.lifecycle_message = (
            "Investigation started."
        )

        updated = repository.update(stored)

        print(
            f"Updated lifecycle: "
            f"{updated.lifecycle_state}"
        )

        deleted = repository.delete(
            incident.incident_id
        )

        if not deleted:
            raise RuntimeError(
                "Repository could not delete the test incident."
            )

        print("Deleted test incident.")

    finally:
        db.close()


if __name__ == "__main__":
    test_repository()
