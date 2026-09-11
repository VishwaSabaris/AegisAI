from typing import Literal

from pydantic import BaseModel, Field


EventType = Literal["Normal", "Warning"]


class PodStatusEvidence(BaseModel):
    """
    Structured Kubernetes pod status evidence.
    """

    service: str
    namespace: str
    pod: str
    phase: str
    ready: bool
    restart_count: int = Field(ge=0)
    reason: str | None = None
    container_status: str


class PodLogsEvidence(BaseModel):
    """
    Structured Kubernetes pod log evidence.
    """

    service: str
    namespace: str
    logs: list[str] = Field(
        default_factory=list
    )


class KubernetesEvent(BaseModel):
    """
    A single Kubernetes event.
    """

    type: EventType
    reason: str
    message: str


class KubernetesEventsEvidence(BaseModel):
    """
    Structured Kubernetes events evidence.
    """

    service: str
    namespace: str
    events: list[KubernetesEvent] = Field(
        default_factory=list
    )


class ServiceDependencyEvidence(BaseModel):
    """
    Structured Kubernetes Service dependency evidence.

    Describes whether a named Kubernetes Service exists
    and whether it currently exposes endpoints.
    """

    dependency: str
    namespace: str
    exists: bool
    cluster_ip: str | None = None
    ports: list[str] = Field(
        default_factory=list
    )
    endpoints: list[str] = Field(
        default_factory=list
    )


class InvestigationEvidence(BaseModel):
    """
    Complete evidence collected during an investigation.
    """

    pod_status: PodStatusEvidence | None = None
    pod_logs: PodLogsEvidence | None = None
    kubernetes_events: KubernetesEventsEvidence | None = None
    service_dependency: ServiceDependencyEvidence | None = None
