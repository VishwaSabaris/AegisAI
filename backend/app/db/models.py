from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    incident_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    grafana_fingerprint: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )

    service: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    environment: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    recent_log: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    lifecycle_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DETECTED",
    )

    previous_lifecycle_state: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    lifecycle_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    severity: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    evidence: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    next_checks: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    remediation_action: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    remediation_risk: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    requires_approval: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    approval_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    recovery_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

class IncidentLifecycleHistory(Base):
    __tablename__ = "incident_lifecycle_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    incident_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    from_state: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    to_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
