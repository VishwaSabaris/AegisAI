from backend.app.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)
from backend.app.services.orchestrator import IncidentOrchestrator


@celery_app.task(name="aegisai.health_check_task")
def health_check_task() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "aegisai",
    }


@celery_app.task(name="aegisai.process_incident_task")
def process_incident_task(
    incident_data: dict,
    grafana_fingerprint: str | None = None,
) -> dict:
    """
    Process an AegisAI incident asynchronously through
    the existing incident orchestrator.

    This task accepts a complete Incident payload and is
    primarily used for direct/manual incident processing.
    """

    incident = Incident.model_validate(incident_data)

    orchestrator = IncidentOrchestrator()

    workflow = orchestrator.process_incident(
        incident=incident,
        grafana_fingerprint=grafana_fingerprint,
    )

    return {
        "success": True,
        "incident_id": incident.incident_id,
        "workflow": workflow.model_dump(),
        "lifecycle": (
            orchestrator
            .get_lifecycle(incident.incident_id)
            .model_dump()
        ),
    }


@celery_app.task(name="aegisai.process_grafana_incident_task")
def process_grafana_incident_task(
    incident_id: str,
    grafana_fingerprint: str | None = None,
) -> dict:
    """
    Process a previously registered Grafana incident.

    The incident is reloaded from PostgreSQL so the Celery
    worker does not depend on FastAPI process memory.

    The incident should already exist in the DETECTED state
    because the webhook registers it before enqueueing this
    task.
    """

    db = SessionLocal()

    try:
        repository = IncidentRepository(db)

        record = repository.get_by_incident_id(
            incident_id
        )

        if record is None:
            raise ValueError(
                f"Incident not found in PostgreSQL: {incident_id}"
            )

        incident = repository.to_incident(record)

    finally:
        db.close()

    orchestrator = IncidentOrchestrator()

    workflow = orchestrator.process_incident(
        incident=incident,
        grafana_fingerprint=grafana_fingerprint,
    )

    return {
        "success": True,
        "incident_id": incident.incident_id,
        "workflow": workflow.model_dump(),
        "lifecycle": (
            orchestrator
            .get_lifecycle(incident.incident_id)
            .model_dump()
        ),
    }
