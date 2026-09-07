from backend.app.agents.investigation import InvestigationAgent
from backend.app.agents.remediation import RemediationAgent
from backend.app.models.incident import Incident
from backend.app.models.orchestration import (
    IncidentWorkflowResult,
)
from backend.app.models.remediation import (
    RemediationAction,
    RemediationRequest,
)


class IncidentOrchestrator:
    """
    Coordinates the AegisAI incident lifecycle.

    The orchestrator is responsible for workflow control.

    It does not allow the LLM to directly execute
    infrastructure-changing operations.
    """

    def __init__(self) -> None:
        self.investigation_agent = (
            InvestigationAgent()
        )

        self.remediation_agent = (
            RemediationAgent()
        )

    @staticmethod
    def _validate_remediation_action(
        action: str,
    ) -> RemediationAction:
        """
        Validate the remediation action proposed by the LLM.

        Only actions explicitly supported by AegisAI are allowed
        to cross into the remediation layer.
        """

        supported_actions = {
            "restart_deployment",
            "rollback_deployment",
            "scale_deployment",
        }

        if action not in supported_actions:
            raise ValueError(
                "Gemma proposed an unsupported remediation action: "
                f"'{action}'. "
                f"Supported actions: "
                f"{sorted(supported_actions)}"
            )

        return action  # type: ignore[return-value]

    def process_incident(
        self,
        incident: Incident,
    ) -> IncidentWorkflowResult:
        """
        Investigate an incident, analyze it with Gemma,
        and evaluate the proposed remediation.

        No infrastructure-changing action is executed.
        """

        analysis = (
            self.investigation_agent.investigate(
                incident
            )
        )

        remediation_action = (
            self._validate_remediation_action(
                analysis.remediation.action
            )
        )

        remediation_request = RemediationRequest(
            action=remediation_action,
            service=incident.service,
            namespace=incident.namespace,
            reason=(
                f"Gemma proposed remediation for "
                f"{incident.service}: "
                f"{analysis.root_cause}"
            ),
        )

        risk_decision = (
            self.remediation_agent.evaluate(
                remediation_request
            )
        )

        return IncidentWorkflowResult(
            stage="approval_required",
            incident=incident.service,
            analysis=analysis,
            risk_decision=risk_decision,
            approval_required=(
                risk_decision.requires_approval
            ),
            remediation_executed=False,
            recovery_status=None,
        )
