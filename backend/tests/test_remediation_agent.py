from backend.app.agents.remediation import (
    RemediationAgent,
)
from backend.app.models.remediation import (
    RemediationRequest,
)


def main():
    print("=" * 60)
    print("AegisAI - Controlled Remediation Agent Test")
    print("=" * 60)

    agent = RemediationAgent()

    print("\nRegistered remediation tools:")
    print(
        agent.registry.describe_tools()
    )

    request = RemediationRequest(
        action="restart_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason=(
            "Payment service is in CrashLoopBackOff."
        ),
    )

    print("\nRemediation request:")
    print(
        request.model_dump_json(
            indent=2
        )
    )

    decision = agent.evaluate(
        request
    )

    print("\nRisk decision:")
    print(
        decision.model_dump_json(
            indent=2
        )
    )

    assert decision.risk == "medium"
    assert decision.requires_approval is True
    assert decision.allowed is False

    print("\nAttempting remediation WITHOUT approval...")

    result = agent.execute(
        request=request,
        approved=False,
    )

    print("\nExecution result:")
    print(
        result
    )

    assert result["success"] is False

    assert (
        "approval"
        in result["error"].lower()
    )

    history = (
        agent.registry.get_execution_history()
    )

    assert len(history) == 0

    print(
        "\nRemediation correctly blocked."
    )

    print(
        "No Kubernetes write tool was executed."
    )

    print(
        "Execution history remains empty."
    )

    print("\nAll assertions passed.")

    print(
        "\nControlled Remediation Agent safety "
        "boundary is working correctly."
    )


if __name__ == "__main__":
    main()
