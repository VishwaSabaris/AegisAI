from typing import Literal

from pydantic import BaseModel, Field

from backend.app.models.incident import IncidentAnalysis
from backend.app.models.remediation import RiskDecision


IncidentStage = Literal[
    "investigation",
    "analysis",
    "remediation_evaluation",
    "approval_required",
    "completed",
]


class IncidentWorkflowResult(BaseModel):
    """
    Represents the result of an AegisAI incident workflow.

    The orchestrator coordinates investigation, AI analysis,
    and deterministic remediation evaluation.

    It does not execute infrastructure-changing actions.
    """

    stage: IncidentStage

    incident: str = Field(
        ...,
        min_length=1,
        description="Service associated with the incident.",
    )

    analysis: IncidentAnalysis

    risk_decision: RiskDecision | None = None

    approval_required: bool

    remediation_executed: bool = False

    recovery_status: str | None = None
