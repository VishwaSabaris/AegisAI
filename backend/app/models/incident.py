from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]

RemediationAction = Literal[
    "restart_deployment",
    "rollback_deployment",
    "scale_deployment",
]


class Incident(BaseModel):
    incident_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        description="Unique identifier for the incident.",
    )

    service: str = Field(
        ...,
        description="Name of the affected service.",
    )

    namespace: str = Field(
        default="default",
        description="Kubernetes namespace where the service is running.",
    )

    environment: str = Field(
        ...,
        description="Environment where the incident occurred.",
    )

    status: str = Field(
        ...,
        description="Current incident status.",
    )

    recent_log: str = Field(
        ...,
        description=(
            "Most recent relevant application or infrastructure log."
        ),
    )


class RemediationProposal(BaseModel):
    action: RemediationAction = Field(
        ...,
        description=(
            "One supported Kubernetes remediation action. "
            "Must be exactly one of: "
            "restart_deployment, rollback_deployment, "
            "scale_deployment."
        ),
    )

    risk: RiskLevel = Field(
        ...,
        description="Risk level associated with the remediation.",
    )

    requires_approval: bool = Field(
        ...,
        description=(
            "Whether human approval is required before execution."
        ),
    )


class IncidentAnalysis(BaseModel):
    severity: Severity = Field(
        ...,
        description="Severity of the incident.",
    )

    root_cause: str = Field(
        ...,
        description="Most likely root cause of the incident.",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence between 0 and 1.",
    )

    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence supporting the root-cause analysis."
        ),
    )

    next_checks: list[str] = Field(
        default_factory=list,
        description=(
            "Checks that should be performed next."
        ),
    )

    remediation: RemediationProposal
