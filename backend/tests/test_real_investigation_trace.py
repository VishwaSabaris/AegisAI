from backend.app.agents.investigation import InvestigationAgent
from backend.app.models.incident import Incident


def main():
    print("=" * 60)
    print("AegisAI - Real Investigation Execution Trace Test")
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

    agent = InvestigationAgent()

    print("\nStarting real investigation...")

    evidence = agent.collect_evidence(incident)

    print("\nEvidence collected successfully.")

    assert evidence.pod_status is not None
    assert evidence.pod_logs is not None
    assert evidence.kubernetes_events is not None

    history = agent.registry.get_execution_history()

    print("\nTool execution history:")
    print("-" * 60)

    for record in history:
        print(
            f"Tool: {record.tool_name}"
        )
        print(
            f"Arguments: {record.arguments}"
        )
        print(
            f"Success: {record.success}"
        )
        print(
            f"Duration: {record.duration_ms:.2f} ms"
        )
        print(
            f"Error: {record.error}"
        )
        print("-" * 60)

    assert len(history) == 3

    tool_names = [
        record.tool_name
        for record in history
    ]

    assert "get_pod_status" in tool_names
    assert "get_pod_logs" in tool_names
    assert "get_kubernetes_events" in tool_names

    for record in history:
        assert record.success is True
        assert record.duration_ms >= 0
        assert record.error is None

        assert record.arguments["service"] == (
            "payment-service"
        )

        assert record.arguments["namespace"] == (
            "aegis-demo"
        )

    print(
        "\nAll three real Kubernetes tool executions "
        "were recorded successfully."
    )

    print("\nExecution order:")

    for index, record in enumerate(history, start=1):
        print(
            f"{index}. {record.tool_name} "
            f"({record.duration_ms:.2f} ms)"
        )

    print("\nAll assertions passed.")

    print(
        "Real Investigation Agent execution tracing "
        "is working correctly."
    )


if __name__ == "__main__":
    main()
