from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import and_, func
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
        grafana_fingerprint: str | None = None,
    ) -> IncidentRecord:
        """
        Create and persist a new incident.

        A Grafana fingerprint can be stored when the
        incident originated from a Grafana alert.
        """

        record = IncidentRecord(
            incident_id=incident.incident_id,
            grafana_fingerprint=grafana_fingerprint,
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
    # READ - GRAFANA FINGERPRINT
    # =========================================================

    def get_by_grafana_fingerprint(
        self,
        grafana_fingerprint: str,
    ) -> IncidentRecord | None:
        """
        Retrieve an incident created from a specific
        Grafana alert fingerprint.
        """

        return (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.grafana_fingerprint
                == grafana_fingerprint
            )
            .first()
        )

    # =========================================================
    # READ - ACTIVE GRAFANA INCIDENT
    # =========================================================

    def get_active_grafana_incident(
        self,
        service: str,
        namespace: str,
    ) -> IncidentRecord | None:
        """
        Retrieve the newest active Grafana-originated
        incident for the specified service and namespace.

        This provides a second deduplication layer when
        Grafana sends a different fingerprint for what is
        still the same active operational problem.
        """

        active_states = [
            "DETECTED",
            "INVESTIGATING",
            "ANALYZED",
            "AWAITING_APPROVAL",
            "APPROVED",
            "EXECUTING",
            "VERIFYING",
        ]

        return (
            self.db.query(IncidentRecord)
            .filter(
                and_(
                    IncidentRecord.grafana_fingerprint.isnot(None),
                    IncidentRecord.service == service,
                    IncidentRecord.namespace == namespace,
                    IncidentRecord.lifecycle_state.in_(
                        active_states
                    ),
                )
            )
            .order_by(
                IncidentRecord.created_at.desc()
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
    # READ - PAGINATED / FILTERED INCIDENTS
    # =========================================================

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        service: str | None = None,
        namespace: str | None = None,
        lifecycle_state: str | None = None,
    ) -> tuple[list[IncidentRecord], int, int]:
        """
        Retrieve incidents using pagination and optional filters.

        Returns:
            (
                records,
                total_count,
                total_pages,
            )

        Results are ordered newest first.
        """

        query = self.db.query(IncidentRecord)

        # -----------------------------------------------------
        # Optional filters
        # -----------------------------------------------------

        if service is not None:
            query = query.filter(
                IncidentRecord.service == service
            )

        if namespace is not None:
            query = query.filter(
                IncidentRecord.namespace == namespace
            )

        if lifecycle_state is not None:
            query = query.filter(
                IncidentRecord.lifecycle_state
                == lifecycle_state
            )

        # -----------------------------------------------------
        # Count matching records before pagination
        # -----------------------------------------------------

        total_count = query.count()

        total_pages = (
            ceil(total_count / page_size)
            if total_count > 0
            else 0
        )

        # -----------------------------------------------------
        # Pagination
        # -----------------------------------------------------

        offset = (page - 1) * page_size

        records = (
            query
            .order_by(
                IncidentRecord.id.desc()
            )
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return (
            records,
            total_count,
            total_pages,
        )

    # =========================================================
    # DASHBOARD SUMMARY
    # =========================================================

    def get_dashboard_summary(
        self,
    ) -> dict:
        """
        Retrieve aggregate incident statistics
        required by the dashboard.

        Returns:
            Dictionary containing:

            - total_incidents
            - active_incidents
            - recovered_incidents
            - failed_incidents
            - pending_approval
            - severity_distribution
            - lifecycle_distribution
        """

        # -----------------------------------------------------
        # Total incidents
        # -----------------------------------------------------

        total_incidents = (
            self.db.query(IncidentRecord)
            .count()
        )

        # -----------------------------------------------------
        # Active incidents
        #
        # These states represent incidents that have not
        # reached a terminal state yet.
        # -----------------------------------------------------

        active_states = [
            "DETECTED",
            "INVESTIGATING",
            "ANALYZED",
            "AWAITING_APPROVAL",
            "APPROVED",
            "EXECUTING",
            "VERIFYING",
        ]

        active_incidents = (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.lifecycle_state.in_(
                    active_states
                )
            )
            .count()
        )

        # -----------------------------------------------------
        # Recovered incidents
        # -----------------------------------------------------

        recovered_incidents = (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.lifecycle_state
                == "RECOVERED"
            )
            .count()
        )

        # -----------------------------------------------------
        # Failed incidents
        # -----------------------------------------------------

        failed_incidents = (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.lifecycle_state
                == "FAILED"
            )
            .count()
        )

        # -----------------------------------------------------
        # Incidents waiting for human approval
        # -----------------------------------------------------

        pending_approval = (
            self.db.query(IncidentRecord)
            .filter(
                IncidentRecord.lifecycle_state
                == "AWAITING_APPROVAL"
            )
            .count()
        )

        # -----------------------------------------------------
        # Severity distribution
        #
        # Ignore incidents that have not been analyzed yet
        # and therefore have no severity value.
        # -----------------------------------------------------

        severity_rows = (
            self.db.query(
                IncidentRecord.severity,
            )
            .filter(
                IncidentRecord.severity.isnot(None)
            )
            .all()
        )

        severity_distribution: dict[str, int] = {}

        for (severity,) in severity_rows:
            severity_distribution[severity] = (
                severity_distribution.get(
                    severity,
                    0,
                )
                + 1
            )

        # -----------------------------------------------------
        # Lifecycle distribution
        # -----------------------------------------------------

        lifecycle_rows = (
            self.db.query(
                IncidentRecord.lifecycle_state,
            )
            .all()
        )

        lifecycle_distribution: dict[str, int] = {}

        for (lifecycle_state,) in lifecycle_rows:
            lifecycle_distribution[lifecycle_state] = (
                lifecycle_distribution.get(
                    lifecycle_state,
                    0,
                )
                + 1
            )

        # -----------------------------------------------------
        # Return dashboard summary
        # -----------------------------------------------------

        return {
            "total_incidents": total_incidents,
            "active_incidents": active_incidents,
            "recovered_incidents": recovered_incidents,
            "failed_incidents": failed_incidents,
            "pending_approval": pending_approval,
            "severity_distribution": severity_distribution,
            "lifecycle_distribution": lifecycle_distribution,
        }

    # =========================================================
    # DASHBOARD - INCIDENT TREND
    # =========================================================

    def get_incident_trend(
        self,
        days: int = 7,
    ) -> list[dict[str, int | str]]:
        """
        Retrieve daily incident counts for the requested
        number of calendar days.

        Days with no incidents are included with a count of 0.

        Results are returned in chronological order.
        """

        if days < 1:
            raise ValueError(
                "days must be greater than or equal to 1."
            )

        now = datetime.now(timezone.utc)

        start_date = (
            now.date()
            - timedelta(days=days - 1)
        )

        start_datetime = datetime.combine(
            start_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        rows = (
            self.db.query(
                func.date(
                    IncidentRecord.created_at
                ).label(
                    "incident_date"
                ),
                func.count(
                    IncidentRecord.id
                ).label(
                    "incident_count"
                ),
            )
            .filter(
                IncidentRecord.created_at
                >= start_datetime
            )
            .group_by(
                func.date(
                    IncidentRecord.created_at
                )
            )
            .order_by(
                func.date(
                    IncidentRecord.created_at
                )
            )
            .all()
        )

        counts = {
            incident_date.isoformat(): int(
                incident_count
            )
            for incident_date, incident_count in rows
        }

        return [
            {
                "date": (
                    start_date
                    + timedelta(days=offset)
                ).isoformat(),
                "count": counts.get(
                    (
                        start_date
                        + timedelta(days=offset)
                    ).isoformat(),
                    0,
                ),
            }
            for offset in range(days)
        ]

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
