from backend.app.llm_client import ask_gemma
from backend.app.models.evidence import (
    InvestigationEvidence,
    KubernetesEvent,
    KubernetesEventsEvidence,
    PodLogsEvidence,
    PodStatusEvidence,
)
from backend.app.models.incident import Incident, IncidentAnalysis
from backend.app.tools.kubernetes import (
    get_kubernetes_events,
    get_pod_logs,
    get_pod_status,
)
from backend.app.tools.registry import ToolRegistry


class InvestigationAgent:
    """
    AegisAI Investigation Agent.

    Collects real Kubernetes evidence through explicitly
    registered read-only tools and sends the validated
    evidence to the local Gemma model.
    """

    def __init__(self) -> None:
        self.registry = ToolRegistry()

        self.registry.register(
            name="get_pod_status",
            function=get_pod_status,
            description=(
                "Retrieve the current status of a Kubernetes pod "
                "associated with a service."
            ),
            permission="read_only",
            requires_approval=False,
        )

        self.registry.register(
            name="get_pod_logs",
            function=get_pod_logs,
            description=(
                "Retrieve recent logs from a Kubernetes pod."
            ),
            permission="read_only",
            requires_approval=False,
        )

        self.registry.register(
            name="get_kubernetes_events",
            function=get_kubernetes_events,
            description=(
                "Retrieve Kubernetes events associated with a service."
            ),
            permission="read_only",
            requires_approval=False,
        )

    def collect_evidence(
        self,
        incident: Incident,
    ) -> InvestigationEvidence:
        """
        Collect and validate real Kubernetes evidence.
        """

        pod_status_result = self.registry.call(
            "get_pod_status",
            service=incident.service,
            namespace=incident.namespace,
        )

        pod_logs_result = self.registry.call(
            "get_pod_logs",
            service=incident.service,
            namespace=incident.namespace,
        )

        events_result = self.registry.call(
            "get_kubernetes_events",
            service=incident.service,
            namespace=incident.namespace,
        )

        pod_status = None

        if pod_status_result["success"]:
            pod_status = PodStatusEvidence.model_validate(
                pod_status_result["data"]
            )

        pod_logs = None

        if pod_logs_result["success"]:
            pod_logs = PodLogsEvidence.model_validate(
                pod_logs_result["data"]
            )

        kubernetes_events = None

        if events_result["success"]:
            kubernetes_events = KubernetesEventsEvidence(
                service=events_result["data"]["service"],
                namespace=events_result["data"]["namespace"],
                events=[
                    KubernetesEvent.model_validate(event)
                    for event in events_result["data"]["events"]
                ],
            )

        return InvestigationEvidence(
            pod_status=pod_status,
            pod_logs=pod_logs,
            kubernetes_events=kubernetes_events,
        )

    def investigate(
        self,
        incident: Incident,
    ) -> IncidentAnalysis:
        """
        Collect real infrastructure evidence and produce
        a validated AI incident analysis.
        """

        evidence = self.collect_evidence(incident)

        return ask_gemma(
            incident=incident,
            evidence=evidence,
        )
