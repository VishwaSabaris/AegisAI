import os
from typing import Any

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Header,
    HTTPException,
    status,
)

from backend.app.core.database import SessionLocal
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)
from backend.app.services.orchestrator import IncidentOrchestrator

load_dotenv()

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)

_orchestrator = IncidentOrchestrator()


def _process_grafana_incident(
    incident: Incident,
    grafana_fingerprint: str | None,
) -> None:
    """
    Process a Grafana incident in the FastAPI background task.

    The webhook itself only registers the incident as DETECTED.
    The expensive investigation, LLM inference, analysis, and
    approval workflow run after the HTTP response has been sent.

    If unexpected processing fails, the incident lifecycle is
    explicitly persisted as FAILED so it cannot remain stuck
    indefinitely in an intermediate state.
    """

    try:
        _orchestrator.process_incident(
            incident=incident,
            grafana_fingerprint=grafana_fingerprint,
        )

    except Exception as error:
        print(
            "Error while processing Grafana incident "
            f"{incident.incident_id}: {error}"
        )

        # -----------------------------------------------------
        # Persist unexpected background-processing failure
        # -----------------------------------------------------

        try:
            lifecycle = _orchestrator.get_lifecycle(
                incident.incident_id
            )

            lifecycle.transition(
                "FAILED",
                message=(
                    "Unexpected error occurred while "
                    "processing the incident in the background."
                ),
            )

            _orchestrator._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                recovery_status="NOT_RECOVERED",
            )

            print(
                "Grafana incident marked as FAILED: "
                f"{incident.incident_id}"
            )

        except Exception as failure_error:
            print(
                "Error while persisting FAILED state for "
                f"Grafana incident {incident.incident_id}: "
                f"{failure_error}"
            )


@router.post(
    "/grafana",
    status_code=status.HTTP_202_ACCEPTED,
)
def grafana_webhook(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    x_aegisai_webhook_secret: str | None = Header(
        default=None,
    ),
) -> dict[str, Any]:
    """
    Receive Grafana Alerting webhook payloads.

    The webhook requires the configured AegisAI shared
    secret and uses two levels of idempotency:

    1. Grafana fingerprint matching.
    2. Active incident matching by service and namespace.

    New incidents are persisted immediately as DETECTED and
    expensive incident processing is scheduled as a background
    task so Grafana does not have to wait for LLM inference.

    Infrastructure-changing remediation remains protected by
    the existing deterministic risk policy and human approval
    boundary.
    """

    expected_secret = os.getenv(
        "AEGISAI_GRAFANA_WEBHOOK_SECRET"
    )

    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Grafana webhook secret is not configured.",
        )

    if x_aegisai_webhook_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Grafana webhook secret.",
        )

    alerts = payload.get("alerts", [])

    if not alerts:
        return {
            "success": True,
            "source": "grafana",
            "message": "Grafana alert received.",
            "alert_count": 0,
            "incidents_created": 0,
            "duplicates_ignored": 0,
        }

    created_incidents: list[dict[str, Any]] = []
    duplicate_incidents: list[dict[str, Any]] = []

    for alert in alerts:
        alert_status = str(
            alert.get("status", "")
        ).lower()

        if alert_status != "firing":
            continue

        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}

        fingerprint = str(
            alert.get("fingerprint") or ""
        ).strip()

        service = str(
            labels.get("service")
            or labels.get("app")
            or "unknown-service"
        )

        namespace = str(
            labels.get("namespace")
            or "default"
        )

        severity = str(
            labels.get("severity")
            or "unknown"
        )

        summary = str(
            annotations.get("summary")
            or labels.get("alertname")
            or "Grafana alert"
        )

        description = str(
            annotations.get("description")
            or summary
        )

        recent_log = (
            f"Grafana alert: {summary}. "
            f"Severity: {severity}. "
            f"Details: {description}"
        )

        db = SessionLocal()

        try:
            repository = IncidentRepository(db)

            existing_record = None

            # -------------------------------------------------
            # First idempotency check:
            # exact Grafana fingerprint
            # -------------------------------------------------

            if fingerprint:
                existing_record = (
                    repository.get_by_grafana_fingerprint(
                        fingerprint
                    )
                )

            # -------------------------------------------------
            # Second idempotency check:
            # existing active incident for service/namespace
            # -------------------------------------------------

            if existing_record is None:
                existing_record = (
                    repository.get_active_grafana_incident(
                        service=service,
                        namespace=namespace,
                    )
                )

        finally:
            db.close()

        if existing_record is not None:
            duplicate_incidents.append(
                {
                    "incident_id": (
                        existing_record.incident_id
                    ),
                    "service": existing_record.service,
                    "namespace": existing_record.namespace,
                    "fingerprint": (
                        fingerprint or None
                    ),
                    "existing_fingerprint": (
                        existing_record.grafana_fingerprint
                    ),
                    "lifecycle_state": (
                        existing_record.lifecycle_state
                    ),
                    "message": (
                        "Duplicate Grafana alert ignored. "
                        "An active incident already exists "
                        "for this service and namespace."
                    ),
                }
            )

            continue

        # -----------------------------------------------------
        # Create incident
        # -----------------------------------------------------

        incident = Incident(
            service=service,
            namespace=namespace,
            environment="kubernetes",
            status=summary,
            recent_log=recent_log,
        )

        # -----------------------------------------------------
        # Register immediately as DETECTED
        # -----------------------------------------------------

        lifecycle = _orchestrator.register_incident(
            incident=incident,
            grafana_fingerprint=(
                fingerprint or None
            ),
        )

        # -----------------------------------------------------
        # Schedule expensive processing in background
        # -----------------------------------------------------

        background_tasks.add_task(
            _process_grafana_incident,
            incident,
            fingerprint or None,
        )

        created_incidents.append(
            {
                "incident_id": incident.incident_id,
                "service": incident.service,
                "namespace": incident.namespace,
                "fingerprint": (
                    fingerprint or None
                ),
                "status": "accepted",
                "lifecycle": lifecycle.model_dump(),
                "message": (
                    "Grafana alert accepted. "
                    "Incident processing scheduled "
                    "in the background."
                ),
            }
        )

    return {
        "success": True,
        "source": "grafana",
        "message": "Grafana alerts accepted for processing.",
        "alert_count": len(alerts),
        "incidents_created": len(created_incidents),
        "duplicates_ignored": len(duplicate_incidents),
        "incidents": created_incidents,
        "duplicates": duplicate_incidents,
    }
