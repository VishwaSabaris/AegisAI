from typing import Literal

from pydantic import BaseModel, Field


RemediationAction = Literal[
    "restart_deployment",
    "rollback_deployment",
    "scale_deployment",
]


class RemediationRequest(BaseModel):
    """
    Represents a requested infrastructure remediation.

    This model describes WHAT should be changed.
    It does not execute anything.
    """

    action: RemediationAction

    service: str = Field(
        ...,
        min_length=1,
        description="Kubernetes service/deployment name.",
    )

    namespace: str = Field(
        default="default",
        min_length=1,
        description="Kubernetes namespace.",
    )

    reason: str = Field(
        ...,
        min_length=1,
        description="Reason for requesting remediation.",
    )


class RiskDecision(BaseModel):
    """
    Deterministic decision produced by the remediation
    safety policy.
    """

    action: RemediationAction
    risk: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]

    requires_approval: bool

    allowed: bool

    reason: str


class RemediationApproval(BaseModel):
    """
    Represents human approval for a remediation request.
    """

    approved: bool

    approved_by: str | None = None

    comment: str | None = None
