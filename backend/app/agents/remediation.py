from backend.app.models.remediation import (
    RemediationRequest,
    RiskDecision,
)
from backend.app.services.metrics import (
    RECOVERY_RESULTS_TOTAL,
    REMEDIATION_ATTEMPTS_TOTAL,
    REMEDIATION_RESULTS_TOTAL,
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

        REMEDIATION_ATTEMPTS_TOTAL.labels(
            action=request.action
        ).inc()

        if request.action == "restart_deployment":
            result = self.registry.call(
                "restart_deployment",
                service=request.service,
                namespace=request.namespace,
                approved=approved,
            )

            result_label = (
                "success"
                if result.get("success") is True
                else "failure"
            )

            REMEDIATION_RESULTS_TOTAL.labels(
                action=request.action,
                result=result_label,
            ).inc()

            return result

        result = {
            "success": False,
            "action": request.action,
            "service": request.service,
            "namespace": request.namespace,
            "error": (
                f"Remediation action '{request.action}' "
                "is not implemented yet."
            ),
        }

        REMEDIATION_RESULTS_TOTAL.labels(
            action=request.action,
            result="failure",
        ).inc()

        return result

    def verify(
        self,
        service: str,
        namespace: str = "default",
    ) -> dict:
        """
        Verify the Kubernetes deployment after remediation.

        Verification is read-only and does not require approval.
        """

        result = self.registry.call(
            "verify_deployment",
            service=service,
            namespace=namespace,
        )

        recovery_status = (
            result.get("data", {})
            .get("recovery_status")
        )

        if recovery_status == "RECOVERED":
            status_label = "recovered"
        elif recovery_status == "NOT_RECOVERED":
            status_label = "not_recovered"
        else:
            status_label = "unknown"

        RECOVERY_RESULTS_TOTAL.labels(
            status=status_label
        ).inc()

        return result
