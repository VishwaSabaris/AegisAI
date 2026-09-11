from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.incident import Incident
from backend.app.models.remediation import RemediationApproval
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)
from backend.app.services.orchestrator import IncidentOrchestrator


router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)


class CreateIncidentRequest(BaseModel):
    service: str = Field(..., min_length=1)
    namespace: str = Field(default="default", min_length=1)
    environment: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    recent_log: str = Field(..., min_length=1)


class ApprovalRequest(BaseModel):
    approved: bool
    approved_by: str | None = None
    comment: str | None = None


_orchestrator = IncidentOrchestrator()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    request: CreateIncidentRequest,
) -> dict[str, Any]:
    """
    Create and process a new incident.

    Incident investigation, AI analysis, risk evaluation,
    lifecycle transitions, and persistence are handled by
    the orchestrator.
    """

    incident = Incident(
        service=request.service,
        namespace=request.namespace,
        environment=request.environment,
        status=request.status,
        recent_log=request.recent_log,
    )

    workflow = _orchestrator.process_incident(
        incident
    )

    return {
        "success": True,
        "incident_id": incident.incident_id,
        "service": incident.service,
        "namespace": incident.namespace,
        "workflow": workflow.model_dump(),
        "lifecycle": (
            _orchestrator
            .get_lifecycle(incident.incident_id)
            .model_dump()
        ),
    }


@router.get("")
def list_incidents(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number starting from 1.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of incidents per page.",
    ),
    service: str | None = Query(
        default=None,
        min_length=1,
        description="Filter incidents by service.",
    ),
    namespace: str | None = Query(
        default=None,
        min_length=1,
        description="Filter incidents by Kubernetes namespace.",
    ),
    lifecycle_state: str | None = Query(
        default=None,
        min_length=1,
        description="Filter incidents by lifecycle state.",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return persisted incidents using database-level
    pagination and optional filters.

    Results are returned newest first.
    """

    repository = IncidentRepository(db)

    (
        records,
        total_count,
        total_pages,
    ) = repository.get_paginated(
        page=page,
        page_size=page_size,
        service=service,
        namespace=namespace,
        lifecycle_state=lifecycle_state,
    )

    return {
        "success": True,
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": total_pages,
        "filters": {
            "service": service,
            "namespace": namespace,
            "lifecycle_state": lifecycle_state,
        },
        "incidents": [
            {
                "incident_id": record.incident_id,
                "service": record.service,
                "namespace": record.namespace,
                "environment": record.environment,
                "status": record.status,
                "lifecycle_state": (
                    record.lifecycle_state
                ),
                "severity": record.severity,
                "root_cause": record.root_cause,
                "confidence": record.confidence,
                "remediation_action": (
                    record.remediation_action
                ),
                "remediation_risk": (
                    record.remediation_risk
                ),
                "requires_approval": (
                    record.requires_approval
                ),
                "approval_status": (
                    record.approval_status
                ),
                "recovery_status": (
                    record.recovery_status
                ),
                "created_at": (
                    record.created_at.isoformat()
                ),
                "updated_at": (
                    record.updated_at.isoformat()
                ),
            }
            for record in records
        ],
    }


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return a persisted incident together with its
    current lifecycle and available workflow state.
    """

    repository = IncidentRepository(db)

    record = repository.get_by_incident_id(
        incident_id
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}",
        )

    incident = repository.to_incident(record)

    try:
        lifecycle = _orchestrator.get_lifecycle(
            incident_id
        ).model_dump()
    except KeyError:
        lifecycle = {
            "incident_id": incident_id,
            "service": record.service,
            "namespace": record.namespace,
            "state": record.lifecycle_state,
            "previous_state": (
                record.previous_lifecycle_state
            ),
            "message": record.lifecycle_message,
        }

    try:
        workflow = _orchestrator.get_workflow(
            incident_id
        ).model_dump()
    except KeyError:
        workflow = None

    return {
        "success": True,
        "incident": incident.model_dump(),
        "lifecycle": lifecycle,
        "workflow": workflow,
        "approval_status": record.approval_status,
        "recovery_status": record.recovery_status,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.post("/{incident_id}/approval")
def approve_incident(
    incident_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Approve or reject a pending remediation.

    The previously generated analysis and remediation
    request are reused. The incident is not re-analyzed.
    """

    repository = IncidentRepository(db)

    record = repository.get_by_incident_id(
        incident_id
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}",
        )

    incident = repository.to_incident(record)

    approval = RemediationApproval(
        approved=request.approved,
        approved_by=request.approved_by,
        comment=request.comment,
    )

    try:
        result = _orchestrator.approve_and_execute(
            incident=incident,
            approval=approval,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return result
