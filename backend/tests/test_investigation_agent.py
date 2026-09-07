from backend.app.agents.investigation import InvestigationAgent
from backend.app.models.incident import Incident


def main():
    print("=" * 60)
    print("AegisAI - Real Kubernetes Investigation Agent Test")
    print("=" * 60)

    incident = Incident(
        service="payment-service",
        namespace="aegis-demo",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    print("\nIncident:")
    print(incident.model_dump_json(indent=2))

    agent = InvestigationAgent()

    print("\nAvailable tools:")
    print(agent.registry.list_tools())

    print("\nCollecting real Kubernetes investigation evidence...")

    evidence = agent.collect_evidence(incident)

    print("\nInvestigation evidence:")
    print("-" * 60)
    print(evidence.model_dump_json(indent=2))
    print("-" * 60)

    assert evidence.pod_status is not None
    assert evidence.pod_logs is not None
    assert evidence.kubernetes_events is not None

    assert evidence.pod_status.service == "payment-service"
    assert evidence.pod_status.namespace == "aegis-demo"

    assert evidence.pod_status.ready is False

    assert evidence.pod_logs.service == "payment-service"
    assert evidence.pod_logs.namespace == "aegis-demo"

    assert len(evidence.pod_logs.logs) > 0

    log_text = "\n".join(
        evidence.pod_logs.logs
    )

    assert (
        "Database connection refused"
        in log_text
    )

    assert (
        "Application startup failed"
        in log_text
    )

    assert (
        len(evidence.kubernetes_events.events)
        > 0
    )

    event_text = "\n".join(
        event.message
        for event in evidence.kubernetes_events.events
    )

    assert (
        "Back-off restarting failed container"
        in event_text
        or "BackOff" in event_text
    )

    print(
        "\nReal Kubernetes evidence validated successfully."
    )

    print("\nPod status:")
    print(
        f"Pod: {evidence.pod_status.pod}"
    )
    print(
        f"Phase: {evidence.pod_status.phase}"
    )
    print(
        f"Ready: {evidence.pod_status.ready}"
    )
    print(
        f"Restarts: {evidence.pod_status.restart_count}"
    )
    print(
        f"Reason: {evidence.pod_status.reason}"
    )
    print(
        f"Container: "
        f"{evidence.pod_status.container_status}"
    )

    print("\nPod logs:")

    for log in evidence.pod_logs.logs:
        print(f"  {log}")

    print("\nKubernetes events:")

    for event in evidence.kubernetes_events.events:
        print(
            f"  [{event.type}] "
            f"{event.reason}: "
            f"{event.message}"
        )

    print("\nRunning Gemma investigation...")

    analysis = agent.investigate(incident)

    print("\nGemma Incident Analysis:")
    print("=" * 60)
    print(analysis.model_dump_json(indent=2))
    print("=" * 60)

    assert analysis.severity in [
        "low",
        "medium",
        "high",
        "critical",
    ]

    assert isinstance(
        analysis.root_cause,
        str,
    )

    assert (
        0.0
        <= analysis.confidence
        <= 1.0
    )

    assert len(analysis.evidence) > 0

    assert len(analysis.next_checks) > 0

    assert isinstance(
        analysis.remediation.action,
        str,
    )

    assert analysis.remediation.risk in [
        "low",
        "medium",
        "high",
        "critical",
    ]

    print(
        "\nEnd-to-end investigation "
        "validated successfully."
    )

    print("\nAll assertions passed.")

    print(
        "Investigation Agent is now connected "
        "to real Kubernetes + Gemma."
    )


if __name__ == "__main__":
    main()
