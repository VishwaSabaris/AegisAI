from backend.app.agents.investigation import InvestigationAgent
from backend.app.agents.remediation import RemediationAgent
from backend.app.models.incident import Incident
from backend.app.models.lifecycle import IncidentLifecycle
from backend.app.models.orchestration import IncidentWorkflowResult
from backend.app.models.remediation import (
    RemediationAction,
    RemediationApproval,
    RemediationRequest,
)
from backend.app.services.lifecycle import IncidentLifecycleManager


class IncidentOrchestrator:
    """
    Coordinates the complete AegisAI incident lifecycle.

    The orchestrator controls the boundary between:

    - incident detection
    - investigation
    - AI analysis
    - remediation evaluation
    - human approval
    - remediation execution
    - recovery verification

    Lifecycle state transitions are deterministic and are never
    controlled directly by the LLM.

    Infrastructure-changing actions require explicit approval.
    """

    def __init__(self) -> None:
        self.investigation_agent = InvestigationAgent()

        self.remediation_agent = RemediationAgent()

        self._lifecycle_managers: dict[
            str,
            IncidentLifecycleManager,
        ] = {}

        self._workflows: dict[
            str,
            IncidentWorkflowResult,
        ] = {}

        self._remediation_requests: dict[
            str,
            RemediationRequest,
        ] = {}

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

    def _get_or_create_lifecycle(
        self,
        incident: Incident,
    ) -> IncidentLifecycleManager:
        """
        Retrieve or create the deterministic lifecycle manager
        for an incident.
        """

        incident_id = incident.incident_id

        if incident_id not in self._lifecycle_managers:
            self._lifecycle_managers[
                incident_id
            ] = IncidentLifecycleManager(
                incident_id=incident.incident_id,
                service=incident.service,
                namespace=incident.namespace,
            )

        return self._lifecycle_managers[incident_id]

    def get_lifecycle(
        self,
        incident_id: str,
    ) -> IncidentLifecycle:
        """
        Return the current lifecycle state for an incident.
        """

        manager = self._lifecycle_managers.get(
            incident_id
        )

        if manager is None:
            raise KeyError(
                f"No lifecycle exists for incident "
                f"'{incident_id}'."
            )

        return manager.lifecycle

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
        Investigate and analyze an incident.

        The resulting workflow is stored so that human approval
        can later execute the exact evaluated remediation request
        without rerunning the investigation.
        """

        lifecycle = self._get_or_create_lifecycle(
            incident
        )

        if lifecycle.state != "DETECTED":
            raise ValueError(
                "Incident cannot be processed from lifecycle state "
                f"'{lifecycle.state}'."
            )

        lifecycle.transition(
            "INVESTIGATING",
            "Incident investigation started.",
        )

        try:
            analysis = (
                self.investigation_agent.investigate(
                    incident
                )
            )

            lifecycle.transition(
                "ANALYZED",
                "Incident investigation and AI analysis completed.",
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

            workflow = IncidentWorkflowResult(
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

            self._workflows[
                incident.incident_id
            ] = workflow

            self._remediation_requests[
                incident.incident_id
            ] = remediation_request

            lifecycle.transition(
                "AWAITING_APPROVAL",
                "Remediation evaluated and is awaiting human approval.",
            )

            return workflow

        except Exception as error:
            if lifecycle.state in {
                "INVESTIGATING",
                "ANALYZED",
            }:
                lifecycle.transition(
                    "FAILED",
                    f"Incident processing failed: {error}",
                )

            raise

    def approve_and_execute(
        self,
        incident: Incident,
        approval: RemediationApproval,
    ) -> dict:
        """
        Process an explicit human approval decision.

        IMPORTANT:

        This method never reruns investigation or Gemma analysis.

        It uses the remediation request already generated during
        process_incident().
        """

        lifecycle = self._get_or_create_lifecycle(
            incident
        )

        if lifecycle.state != "AWAITING_APPROVAL":
            return {
                "success": False,
                "status": "BLOCKED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "Incident is not awaiting approval. "
                    f"Current lifecycle state: "
                    f"{lifecycle.state}"
                ),
            }

        if not approval.approved:
            lifecycle.transition(
                "REJECTED",
                "Remediation rejected by human approval.",
            )

            return {
                "success": False,
                "status": "REJECTED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "approval": approval.model_dump(),
                "lifecycle": lifecycle.lifecycle.model_dump(),
            }

        lifecycle.transition(
            "APPROVED",
            "Remediation explicitly approved by human.",
        )

        workflow = self._workflows.get(
            incident.incident_id
        )

        remediation_request = (
            self._remediation_requests.get(
                incident.incident_id
            )
        )

        if workflow is None:
            lifecycle.transition(
                "FAILED",
                "Stored incident workflow was not found.",
            )

            return {
                "success": False,
                "status": "FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "No stored workflow exists for this incident."
                ),
                "lifecycle": lifecycle.lifecycle.model_dump(),
            }

        if remediation_request is None:
            lifecycle.transition(
                "FAILED",
                "Stored remediation request was not found.",
            )

            return {
                "success": False,
                "status": "FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "error": (
                    "No stored remediation request exists "
                    "for this incident."
                ),
                "lifecycle": lifecycle.lifecycle.model_dump(),
            }

        lifecycle.transition(
            "EXECUTING",
            "Approved remediation execution started.",
        )

        execution = self.remediation_agent.execute(
            request=remediation_request,
            approved=True,
        )

        if not execution["success"]:
            lifecycle.transition(
                "FAILED",
                "Approved remediation execution failed.",
            )

            return {
                "success": False,
                "status": "EXECUTION_FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": False,
                "recovery_status": None,
                "analysis": workflow.analysis.model_dump(),
                "risk_decision": (
                    workflow.risk_decision.model_dump()
                    if workflow.risk_decision
                    else None
                ),
                "execution": execution,
                "approval": approval.model_dump(),
                "lifecycle": lifecycle.lifecycle.model_dump(),
                "error": execution.get(
                    "error",
                    "Remediation execution failed.",
                ),
            }

        lifecycle.transition(
            "VERIFYING",
            "Remediation executed. Recovery verification started.",
        )

        verification = self.remediation_agent.verify(
            service=incident.service,
            namespace=incident.namespace,
        )

        if not verification["success"]:
            lifecycle.transition(
                "FAILED",
                "Recovery verification failed to run.",
            )

            return {
                "success": False,
                "status": "VERIFICATION_FAILED",
                "service": incident.service,
                "namespace": incident.namespace,
                "remediation_executed": True,
                "recovery_status": None,
                "analysis": workflow.analysis.model_dump(),
                "risk_decision": (
                    workflow.risk_decision.model_dump()
                    if workflow.risk_decision
                    else None
                ),
                "execution": execution,
                "verification": verification,
                "approval": approval.model_dump(),
                "lifecycle": lifecycle.lifecycle.model_dump(),
                "error": (
                    "Remediation executed, but recovery "
                    "verification failed to run."
                ),
            }

        recovery_status = (
            verification["data"]["recovery_status"]
        )

        if recovery_status == "RECOVERED":
            lifecycle.transition(
                "RECOVERED",
                "Remediation completed and service recovered.",
            )

            status = "RECOVERED"
            success = True

        else:
            lifecycle.transition(
                "FAILED",
                "Remediation completed but service did not recover.",
            )

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
                if workflow.risk_decision
                else None
            ),
            "execution": execution,
            "verification": verification,
            "approval": approval.model_dump(),
            "lifecycle": lifecycle.lifecycle.model_dump(),
        }
