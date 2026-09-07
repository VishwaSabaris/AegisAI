from backend.app.models.remediation import (
    RemediationAction,
    RemediationRequest,
    RiskDecision,
)


class RemediationRiskPolicy:
    """
    Deterministic safety policy for AegisAI remediation.

    The LLM does not determine whether an action is safe.
    This policy does.
    """

    _POLICIES = {
        "restart_deployment": {
            "risk": "medium",
            "requires_approval": True,
        },
        "rollback_deployment": {
            "risk": "high",
            "requires_approval": True,
        },
        "scale_deployment": {
            "risk": "high",
            "requires_approval": True,
        },
    }

    def evaluate(
        self,
        request: RemediationRequest,
    ) -> RiskDecision:
        """
        Evaluate a remediation request using deterministic rules.
        """

        policy = self._POLICIES.get(
            request.action
        )

        if policy is None:
            raise ValueError(
                f"No remediation policy exists for "
                f"action '{request.action}'."
            )

        return RiskDecision(
            action=request.action,
            risk=policy["risk"],
            requires_approval=policy[
                "requires_approval"
            ],
            allowed=False,
            reason=(
                "Infrastructure-changing remediation "
                "requires explicit human approval before "
                "execution."
            ),
        )

    @classmethod
    def supported_actions(
        cls,
    ) -> list[RemediationAction]:
        """
        Return all remediation actions understood by
        the safety policy.
        """

        return sorted(
            cls._POLICIES.keys()
        )
