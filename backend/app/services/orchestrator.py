from backend.app.agents.investigation import InvestigationAgent
from backend.app.agents.remediation import RemediationAgent
from backend.app.models.incident import Incident
from backend.app.models.orchestration import (
    IncidentWorkflowResult,
)
from backend.app.models.remediation import (
    RemediationAction,
    RemediationApproval,
    RemediationRequest,
)


class IncidentOrchestrator:
    """
    Coordinates the AegisAI incident lifecycle.

    The orchestrator controls the boundary between:
    investigation,
    AI analysis,
    remediation evaluation,
    human approval,
    remediation execution,
    and recovery verification.

    Infrastructure-changing actions are never executed
    without explicit human approval.
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

        Only explicitly supported actions may cross into
        the remediation layer.
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

    def _build_remediation_request(
        self,
        incident: Incident,
        action: RemediationAction,
        reason: str,
    ) -> RemediationRequest:
        """
        Build a validated remediation request.
        """

        return RemediationRequest(
            action=action,
            service=incident.service,
            namespace=incident.namespace,
            reason=reason,
        )

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

        remediation_request = (
            self._build_remediation_request(
                incident=incident,
                action=remediation_action,
                reason=(
                    f"Gemma proposed remediation for "
                    f"{incident.service}: "
                    f"{analysis.root_cause}"
                ),
            )
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

    def approve_and_execute(
        self,
        incident: Incident,
        approval: RemediationApproval,
    ) -> dict:
        """
        Execute a previously evaluated remediation request
        only after explicit human approval.

        Rejected approvals never reach the Kubernetes
        remediation tool.
        """

        if not approval.approved:
            return {
                "success": False,
                "status": "REJECTED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "Remediation rejected by human approval."
                ),
            }

        workflow = self.process_incident(
            incident
        )

        if workflow.risk_decision is None:
            return {
                "success": False,
                "status": "BLOCKED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "No risk decision was generated."
                ),
            }

        if not workflow.approval_required:
            return {
                "success": False,
                "status": "BLOCKED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "Remediation execution policy is invalid: "
                    "approval was expected for an "
                    "infrastructure-changing action."
                ),
            }

        request = RemediationRequest(
            action=workflow.risk_decision.action,
            service=incident.service,
            namespace=incident.namespace,
            reason=(
                f"Approved remediation for "
                f"{incident.service}: "
                f"{workflow.analysis.root_cause}"
            ),
        )

        execution = self.remediation_agent.execute(
            request=request,
            approved=True,
        )

        if not execution["success"]:
            return {
                "success": False,
                "status": "EXECUTION_FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "execution": execution,
                "error": execution.get(
                    "error",
                    "Remediation execution failed.",
                ),
            }

        verification = (
            self.remediation_agent.verify(
                service=incident.service,
                namespace=incident.namespace,
            )
        )

        if not verification["success"]:
            return {
                "success": False,
                "status": "VERIFICATION_FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": True,
                "recovery_status": None,
                "execution": execution,
                "verification": verification,
                "error": (
                    "Remediation executed, but recovery "
                    "verification failed to run."
                ),
            }

        recovery_status = (
            verification["data"]["recovery_status"]
        )

        if recovery_status == "RECOVERED":
            status = "RECOVERED"
            success = True
        else:
            status = "NOT_RECOVERED"
            success = False

        return {
            "success": success,
            "status": status,
            "service": incident.service,
            "namespace": incident.namespace,
            "remediation_executed": True,
            "recovery_status": recovery_status,
            "analysis": workflow.analysis.model_dump(),
            "risk_decision": (
                workflow.risk_decision.model_dump()
            ),
            "execution": execution,
            "verification": verification,
            "approval": approval.model_dump(),
        }
