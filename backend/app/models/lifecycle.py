from typing import Literal

from pydantic import BaseModel, Field


IncidentState = Literal[
    "DETECTED",
    "INVESTIGATING",
    "ANALYZED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXECUTING",
    "VERIFYING",
    "RECOVERED",
    "FAILED",
]


class IncidentLifecycle(BaseModel):
    """
    Represents the current lifecycle state of an AegisAI incident.

    State transitions are controlled by application code,
    not by the LLM.
    """

    incident_id: str = Field(
        ...,
        min_length=1,
    )

    service: str = Field(
        ...,
        min_length=1,
    )

    namespace: str = Field(
        default="default",
        min_length=1,
    )

    state: IncidentState

    previous_state: IncidentState | None = None

    message: str = Field(
        ...,
        min_length=1,
    )
