from sqlalchemy.orm import Session

from backend.app.db.models import IncidentRecord
from backend.app.models.incident import Incident


class IncidentRepository:
    """
    Repository for persistent incident storage.

    Keeps database operations isolated from the
    orchestration and agent layers.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================
    # CREATE
    # =========================================================

    def create(
        self,
        incident: Incident,
    ) -> IncidentRecord:
        """
        Create and persist a new incident.
        """

        record = IncidentRecord(
            incident_id=incident.incident_id,
            service=incident.service,
            namespace=incident.namespace,
            environment=incident.environment,
            status=incident.status,
            recent_log=incident.recent_log,
            lifecycle_state="DETECTED",
            lifecycle_message="Incident detected.",
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

            return record

        except Exception:
            self.db.rollback()
            raise

    # =========================================================
    # READ - SINGLE INCIDENT
    # =========================================================

    def get_by_incident_id(
        self,
        incident_id: str,
    ) -> IncidentRecord | None:
        """
        Retrieve an incident by its unique incident ID.
        """

        return (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident_id == incident_id
            )
            .first()
        )

    # =========================================================
    # READ - ALL INCIDENTS
    # =========================================================

    def get_all(
        self,
    ) -> list[IncidentRecord]:
        """
        Retrieve all persisted incidents.

        Newest incidents are returned first.
        """

        return (
            self.db.query(IncidentRecord)
            .order_by(
                IncidentRecord.id.desc()
            )
            .all()
        )

    # =========================================================
    # READ - BY LIFECYCLE
    # =========================================================

    def get_by_lifecycle_state(
        self,
        lifecycle_state: str,
    ) -> list[IncidentRecord]:
        """
        Retrieve all incidents currently in a
        specific lifecycle state.

        Newest incidents are returned first.
        """

        return (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.lifecycle_state
                == lifecycle_state
            )
            .order_by(
                IncidentRecord.id.desc()
            )
            .all()
        )

    # =========================================================
    # READ - PENDING APPROVALS
    # =========================================================

    def get_pending_approvals(
        self,
    ) -> list[IncidentRecord]:
        """
        Retrieve incidents that are currently
        waiting for human approval.
        """

        return self.get_by_lifecycle_state(
            "AWAITING_APPROVAL"
        )

    # =========================================================
    # CONVERT DATABASE RECORD -> DOMAIN MODEL
    # =========================================================

    def to_incident(
        self,
        record: IncidentRecord,
    ) -> Incident:
        """
        Convert a persisted database record back
        into the application's Incident model.
        """

        return Incident(
            incident_id=record.incident_id,
            service=record.service,
            namespace=record.namespace,
            environment=record.environment,
            status=record.status,
            recent_log=record.recent_log,
        )

    # =========================================================
    # UPDATE
    # =========================================================

    def update(
        self,
        record: IncidentRecord,
    ) -> IncidentRecord:
        """
        Persist modifications to an existing record.
        """

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

            return record

        except Exception:
            self.db.rollback()
            raise

    # =========================================================
    # DELETE
    # =========================================================

    def delete(
        self,
        incident_id: str,
    ) -> bool:
        """
        Delete an incident by incident ID.

        Returns True if an incident was deleted,
        otherwise False.
        """

        record = self.get_by_incident_id(
            incident_id
        )

        if record is None:
            return False

        try:
            self.db.delete(record)
            self.db.commit()

            return True

        except Exception:
            self.db.rollback()
            raise
