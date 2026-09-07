from backend.app.models.remediation import (
    RemediationRequest,
    RiskDecision,
)
from backend.app.services.risk_policy import (
    RemediationRiskPolicy,
)
from backend.app.tools.kubernetes import (
    verify_deployment,
)
from backend.app.tools.remediation import (
    restart_deployment,
)
from backend.app.tools.registry import ToolRegistry


class RemediationAgent:
    """
    AegisAI Remediation Agent.

    Converts remediation requests into controlled tool
    executions while enforcing the deterministic risk
    policy and approval requirement.
    """

    def __init__(self) -> None:
        self.registry = ToolRegistry()

        self.registry.register(
            name="restart_deployment",
            function=restart_deployment,
            description=(
                "Restart a Kubernetes deployment by "
                "changing its pod template."
            ),
            permission="write",
            requires_approval=True,
        )

        self.registry.register(
            name="verify_deployment",
            function=verify_deployment,
            description=(
                "Verify the health and readiness of a "
                "Kubernetes deployment and its pods."
            ),
            permission="read_only",
            requires_approval=False,
        )

        self.risk_policy = RemediationRiskPolicy()

    def evaluate(
        self,
        request: RemediationRequest,
    ) -> RiskDecision:
        """
        Evaluate a remediation request using the
        deterministic risk policy.
        """

        return self.risk_policy.evaluate(
            request
        )

    def execute(
        self,
        request: RemediationRequest,
        approved: bool = False,
    ) -> dict:
        """
        Execute a remediation request only when the
        deterministic policy and explicit approval allow it.
        """

        decision = self.evaluate(
            request
        )

        if (
            decision.requires_approval
            and not approved
        ):
            return {
                "success": False,
                "action": request.action,
                "service": request.service,
                "namespace": request.namespace,
                "error": (
                    "Remediation blocked: explicit human "
                    "approval is required."
                ),
            }

        if request.action == "restart_deployment":
            return self.registry.call(
                "restart_deployment",
                service=request.service,
                namespace=request.namespace,
                approved=approved,
            )

        return {
            "success": False,
            "action": request.action,
            "service": request.service,
            "namespace": request.namespace,
            "error": (
                f"Remediation action '{request.action}' "
                "is not implemented yet."
            ),
        }

    def verify(
        self,
        service: str,
        namespace: str = "default",
    ) -> dict:
        """
        Verify the Kubernetes deployment after remediation.

        Verification is read-only and does not require approval.
        """

        return self.registry.call(
            "verify_deployment",
            service=service,
            namespace=namespace,
        )
