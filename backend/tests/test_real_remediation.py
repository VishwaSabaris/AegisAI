import json
import time

from backend.app.agents.remediation import RemediationAgent
from backend.app.models.remediation import RemediationRequest


SERVICE = "payment-service"
NAMESPACE = "aegis-demo"


def main() -> None:
    print("=" * 60)
    print("AegisAI - Real Kubernetes Remediation Test")
    print("=" * 60)

    agent = RemediationAgent()

    request = RemediationRequest(
        action="restart_deployment",
        service=SERVICE,
        namespace=NAMESPACE,
        reason=(
            "Payment service is in CrashLoopBackOff "
            "and requires controlled remediation."
        ),
    )

    print("\nRemediation request:")
    print(
        json.dumps(
            request.model_dump(),
            indent=2,
        )
    )

    decision = agent.evaluate(
        request
    )

    print("\nRisk decision:")
    print(
        json.dumps(
            decision.model_dump(),
            indent=2,
        )
    )

    assert decision.action == "restart_deployment"
    assert decision.risk == "medium"
    assert decision.requires_approval is True
    assert decision.allowed is False

    print(
        "\nExecuting remediation with explicit approval..."
    )

    result = agent.execute(
        request,
        approved=True,
    )

    print("\nRemediation result:")
    print("-" * 60)
    print(result)
    print("-" * 60)

    assert result["success"] is True
    assert result["action"] == "restart_deployment"

    print(
        "\nKubernetes restart request accepted."
    )

    print(
        "\nWaiting for Kubernetes to process "
        "the deployment restart..."
    )

    time.sleep(5)

    print(
        "\nVerifying deployment..."
    )

    verification = agent.verify(
        service=SERVICE,
        namespace=NAMESPACE,
    )

    print("\nVerification result:")
    print("-" * 60)
    print(verification)
    print("-" * 60)

    assert verification["success"] is True

    data = verification["data"]

    print(
        f"\nDesired replicas: "
        f"{data['desired_replicas']}"
    )

    print(
        f"Updated replicas: "
        f"{data['updated_replicas']}"
    )

    print(
        f"Available replicas: "
        f"{data['available_replicas']}"
    )

    print(
        f"Ready replicas: "
        f"{data['ready_replicas']}"
    )

    print(
        f"Rollout complete: "
        f"{data['rollout_complete']}"
    )

    print(
        f"Recovery status: "
        f"{data['recovery_status']}"
    )

    print(
        f"Recovery reason: "
        f"{data['recovery_reason']}"
    )

    print("\nApplication health:")
    print(
        json.dumps(
            data["application_health"],
            indent=2,
        )
    )

    print("\nKubernetes Warning events:")

    if data["warning_events"]:
        for event in data["warning_events"]:
            print(
                f"  [{event['reason']}] "
                f"{event['message']}"
            )
    else:
        print("  None")

    print("\nStability:")
    print(
        json.dumps(
            data["stability"],
            indent=2,
        )
    )

    print("\nPods:")

    for pod in data["pods"]:
        print(
            f"  Pod: {pod['pod']}"
        )
        print(
            f"  Phase: {pod['phase']}"
        )
        print(
            f"  Ready: {pod['ready']}"
        )
        print(
            f"  Restarts: {pod['restart_count']}"
        )
        print(
            f"  Container: "
            f"{pod['container_status']}"
        )
        print(
            f"  Reason: {pod['reason']}"
        )

    print("\nExecution history:")
    print("-" * 60)

    history = agent.registry.get_execution_history()

    assert len(history) == 2

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
            f"Duration: "
            f"{record.duration_ms:.2f} ms"
        )
        print(
            f"Error: {record.error}"
        )
        print("-" * 60)

    assert history[0].tool_name == (
        "restart_deployment"
    )

    assert history[0].success is True

    assert history[1].tool_name == (
        "verify_deployment"
    )

    assert history[1].success is True

    # The current payment-service deployment is
    # intentionally broken because it requires a
    # nonexistent postgres-service.
    #
    # Therefore the restart itself should succeed,
    # but application recovery must fail.
    assert (
        data["recovery_status"]
        == "NOT_RECOVERED"
    )

    assert data["stability"]["stable"] is False

    assert (
        data["stability"]["observed_seconds"]
        < data["stability"]["required_seconds"]
    )

    print(
        "\nRecovery result: NOT_RECOVERED"
    )

    print(
        "\nExpected behavior confirmed:"
    )

    print(
        "  Remediation execution: SUCCESS"
    )

    print(
        "  Application recovery: NOT_RECOVERED"
    )

    print(
        "\nThe deployment restart succeeded, "
        "but the application remained unhealthy."
    )

    print(
        "\nAll assertions passed."
    )


if __name__ == "__main__":
    main()
