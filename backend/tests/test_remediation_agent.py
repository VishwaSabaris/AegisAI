from backend.app.agents.remediation import RemediationAgent
from backend.app.models.remediation import RemediationRequest


def test_unapproved_remediation_is_blocked() -> None:
    agent = RemediationAgent()

    request = RemediationRequest(
        action="restart_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason="Payment service is in CrashLoopBackOff.",
    )

    result = agent.execute(
        request=request,
        approved=False,
    )

    assert result["success"] is False
    assert "approval" in result["error"].lower()

    history = agent.registry.get_execution_history()

    assert history == []


def test_approved_restart_is_executed(
    monkeypatch,
) -> None:
    agent = RemediationAgent()

    request = RemediationRequest(
        action="restart_deployment",
        service="payment-service",
        namespace="aegis-demo",
        reason="Payment service is in CrashLoopBackOff.",
    )

    calls: list[dict] = []

    def fake_restart_deployment(
        service: str,
        namespace: str,
        approved: bool,
    ) -> dict:
        calls.append(
            {
                "service": service,
                "namespace": namespace,
                "approved": approved,
            }
        )

        return {
            "success": True,
            "service": service,
            "namespace": namespace,
            "action": "restart_deployment",
        }

    monkeypatch.setattr(
        "backend.app.agents.remediation.restart_deployment",
        fake_restart_deployment,
    )

    # The registry stores the function object at registration time,
    # so update the registered tool explicitly for this unit test.
    tool = agent.registry.get("restart_deployment")

    agent.registry._tools[
        "restart_deployment"
    ] = tool.__class__(
        name=tool.name,
        description=tool.description,
        permission=tool.permission,
        requires_approval=tool.requires_approval,
        function=fake_restart_deployment,
    )

    result = agent.execute(
        request=request,
        approved=True,
    )

    assert result["success"] is True

    assert calls == [
        {
            "service": "payment-service",
            "namespace": "aegis-demo",
            "approved": True,
        }
    ]

    history = agent.registry.get_execution_history()

    assert len(history) == 1
    assert history[0].tool_name == "restart_deployment"
    assert history[0].success is True
    assert history[0].arguments == {
        "service": "payment-service",
        "namespace": "aegis-demo",
        "approved": True,
    }


if __name__ == "__main__":
    test_unapproved_remediation_is_blocked()
    print("Unapproved remediation test passed.")
