from backend.app.models.remediation import (
    RemediationRequest,
)
from backend.app.services.risk_policy import (
    RemediationRiskPolicy,
)


def main():
    print("=" * 60)
    print("AegisAI - Remediation Risk Policy Test")
    print("=" * 60)

    policy = RemediationRiskPolicy()

    print("\nSupported remediation actions:")

    for action in policy.supported_actions():
        print(f"  - {action}")

    request = RemediationRequest(
        action="restart_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason=(
            "Payment service is in CrashLoopBackOff "
            "and requires investigation/remediation."
        ),
    )

    print("\nRemediation request:")
    print(
        request.model_dump_json(
            indent=2
        )
    )

    decision = policy.evaluate(
        request
    )

    print("\nRisk decision:")
    print(
        decision.model_dump_json(
            indent=2
        )
    )

    assert decision.action == (
        "restart_deployment"
    )

    assert decision.risk == "medium"

    assert (
        decision.requires_approval
        is True
    )

    assert decision.allowed is False

    assert (
        "human approval"
        in decision.reason
    )

    print(
        "\nRestart deployment correctly classified:"
    )
    print("  Risk: MEDIUM")
    print("  Approval required: YES")
    print("  Execution allowed: NO")

    rollback_request = RemediationRequest(
        action="rollback_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason=(
            "Rollback requested after failed deployment."
        ),
    )

    rollback_decision = policy.evaluate(
        rollback_request
    )

    assert rollback_decision.risk == "high"
    assert (
        rollback_decision.requires_approval
        is True
    )
    assert rollback_decision.allowed is False

    print(
        "\nRollback correctly classified:"
    )
    print("  Risk: HIGH")
    print("  Approval required: YES")
    print("  Execution allowed: NO")

    scale_request = RemediationRequest(
        action="scale_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason=(
            "Scale service to handle increased load."
        ),
    )

    scale_decision = policy.evaluate(
        scale_request
    )

    assert scale_decision.risk == "high"
    assert (
        scale_decision.requires_approval
        is True
    )
    assert scale_decision.allowed is False

    print(
        "\nScale correctly classified:"
    )
    print("  Risk: HIGH")
    print("  Approval required: YES")
    print("  Execution allowed: NO")

    print("\nAll assertions passed.")

    print(
        "\nRemediation Risk Policy is working correctly."
    )

    print(
        "\nNo Kubernetes resources were modified."
    )


if __name__ == "__main__":
    main()
