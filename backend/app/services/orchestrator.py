from typing import cast

from backend.app.agents.investigation import InvestigationAgent
from backend.app.agents.remediation import RemediationAgent
from backend.app.core.database import SessionLocal
from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
    RemediationProposal,
)
from backend.app.models.lifecycle import (
    IncidentLifecycle,
    IncidentState,
)
from backend.app.models.orchestration import (
    IncidentWorkflowResult,
)
from backend.app.models.remediation import (
    RemediationAction,
    RemediationApproval,
    RemediationRequest,
)
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)
from backend.app.services.lifecycle import (
    IncidentLifecycleManager,
)


class IncidentOrchestrator:
    """
    Coordinates the AegisAI incident workflow.

    The LLM performs analysis and proposes remediation.
    Application code controls lifecycle transitions,
    risk evaluation, approval, infrastructure execution,
    and recovery verification.

    Persisted incidents are rehydrated from PostgreSQL when
    the orchestrator starts so that process restarts do not
    lose the current incident lifecycle/workflow state.
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

        self._rehydrate_persisted_incidents()

    # =========================================================
    # Persistence / Rehydration
    # =========================================================

    def _rehydrate_persisted_incidents(self) -> None:
        """
        Restore persisted incident state from PostgreSQL.

        This method intentionally does not call the LLM.

        Persisted incidents are reconstructed from the database
        fields that are currently available.

        Incidents that do not yet have an AI analysis are restored
        only as lifecycle state. Incidents with persisted analysis
        are restored with their workflow and remediation request.
        """

        db = SessionLocal()

        try:
            repository = IncidentRepository(db)
            records = repository.get_all()

            for record in records:
                incident = repository.to_incident(record)

                try:
                    self._restore_incident(
                        incident=incident,
                        record=record,
                    )
                except Exception as exc:
                    # One malformed historical record should not
                    # prevent the orchestrator from starting.
                    print(
                        "Warning: failed to rehydrate incident "
                        f"{record.incident_id}: {exc}"
                    )

        finally:
            db.close()

    def _restore_incident(
        self,
        incident: Incident,
        record,
    ) -> None:
        """
        Restore one persisted incident into runtime state.
        """

        lifecycle = IncidentLifecycleManager(
            incident_id=incident.incident_id,
            service=incident.service,
            namespace=incident.namespace,
        )

        persisted_state = cast(
            IncidentState,
            record.lifecycle_state,
        )

        persisted_previous_state = (
            record.previous_lifecycle_state
        )

        persisted_message = (
            record.lifecycle_message
            or "Incident state restored from PostgreSQL."
        )

        # -----------------------------------------------------
        # Reconstruct lifecycle without replaying transitions.
        #
        # The lifecycle manager normally starts at DETECTED.
        # We replace its internal immutable lifecycle object
        # with the persisted lifecycle snapshot.
        # -----------------------------------------------------

        lifecycle._lifecycle = IncidentLifecycle(
            incident_id=incident.incident_id,
            service=incident.service,
            namespace=incident.namespace,
            state=persisted_state,
            previous_state=cast(
                IncidentState | None,
                persisted_previous_state,
            ),
            message=persisted_message,
        )

        self._lifecycle_managers[
            incident.incident_id
        ] = lifecycle

        # -----------------------------------------------------
        # Restore workflow only when persisted analysis exists.
        # -----------------------------------------------------

        if (
            record.severity is None
            or record.root_cause is None
            or record.confidence is None
            or record.remediation_action is None
            or record.remediation_risk is None
            or record.requires_approval is None
        ):
            return

        action = self._validate_remediation_action(
            record.remediation_action
        )

        remediation = RemediationProposal(
            action=action,
            risk=cast(
                str,
                record.remediation_risk,
            ),
            requires_approval=record.requires_approval,
        )

        analysis = IncidentAnalysis(
            severity=cast(
                str,
                record.severity,
            ),
            root_cause=record.root_cause,
            confidence=record.confidence,
            evidence=[],
            next_checks=[],
            remediation=remediation,
        )

        risk_decision = (
            self.remediation_agent.risk_policy.evaluate(
                RemediationRequest(
                    action=action,
                    service=incident.service,
                    namespace=incident.namespace,
                    reason=record.root_cause,
                )
            )
        )

        workflow_stage = self._workflow_stage_from_state(
            persisted_state
        )

        workflow = IncidentWorkflowResult(
            stage=workflow_stage,
            incident=incident.service,
            analysis=analysis,
            risk_decision=risk_decision,
            approval_required=record.requires_approval,
            remediation_executed=(
                record.approval_status == "APPROVED"
                and record.recovery_status is not None
            ),
            recovery_status=record.recovery_status,
        )

        self._workflows[
            incident.incident_id
        ] = workflow

        remediation_request = RemediationRequest(
            action=action,
            service=incident.service,
            namespace=incident.namespace,
            reason=record.root_cause,
        )

        self._remediation_requests[
            incident.incident_id
        ] = remediation_request

    def _workflow_stage_from_state(
        self,
        state: IncidentState,
    ) -> str:
        """
        Map a persisted lifecycle state to the corresponding
        IncidentWorkflowResult stage.
        """

        if state == "AWAITING_APPROVAL":
            return "approval_required"

        if state in {
            "APPROVED",
            "EXECUTING",
            "VERIFYING",
            "RECOVERED",
            "FAILED",
            "REJECTED",
        }:
            return "remediation_evaluation"

        if state == "ANALYZED":
            return "analysis"

        return "investigation"

    # =========================================================
    # Validation
    # =========================================================

    def _validate_remediation_action(
        self,
        action: str,
    ) -> RemediationAction:
        """
        Validate that the AI selected a supported remediation
        action.
        """

        allowed_actions = {
            "restart_deployment",
            "rollback_deployment",
            "scale_deployment",
        }

        if action not in allowed_actions:
            raise ValueError(
                f"Unsupported remediation action: {action}"
            )

        return cast(
            RemediationAction,
            action,
        )

    # =========================================================
    # Lifecycle
    # =========================================================

    def _get_or_create_lifecycle(
        self,
        incident: Incident,
    ) -> IncidentLifecycleManager:
        """
        Get an existing runtime lifecycle manager or create one.
        """

        if incident.incident_id not in self._lifecycle_managers:
            self._lifecycle_managers[
                incident.incident_id
            ] = IncidentLifecycleManager(
                incident_id=incident.incident_id,
                service=incident.service,
                namespace=incident.namespace,
            )

        return self._lifecycle_managers[
            incident.incident_id
        ]

    def get_lifecycle(
        self,
        incident_id: str,
    ) -> IncidentLifecycle:
        """
        Return the current lifecycle state.
        """

        manager = self._lifecycle_managers.get(
            incident_id
        )

        if manager is None:
            raise KeyError(
                f"No lifecycle found for incident: {incident_id}"
            )

        return manager.lifecycle

    # =========================================================
    # Database Persistence
    # =========================================================

    def _persist_incident(
        self,
        incident: Incident,
        lifecycle: IncidentLifecycleManager,
        workflow: IncidentWorkflowResult | None = None,
        approval_status: str | None = None,
        recovery_status: str | None = None,
    ) -> None:
        """
        Persist the current incident state to PostgreSQL.
        """

        db = SessionLocal()

        try:
            repository = IncidentRepository(db)

            record = repository.get_by_incident_id(
                incident.incident_id
            )

            if record is None:
                record = repository.create(
                    incident
                )

            current_lifecycle = lifecycle.lifecycle

            record.lifecycle_state = (
                current_lifecycle.state
            )

            record.previous_lifecycle_state = (
                current_lifecycle.previous_state
            )

            record.lifecycle_message = (
                current_lifecycle.message
            )

            if workflow is not None:
                analysis = workflow.analysis

                record.severity = analysis.severity
                record.root_cause = analysis.root_cause
                record.confidence = analysis.confidence

                if workflow.risk_decision is not None:
                    record.remediation_action = (
                        workflow.risk_decision.action
                    )

                    record.remediation_risk = (
                        workflow.risk_decision.risk
                    )

                    record.requires_approval = (
                        workflow.risk_decision.requires_approval
                    )

            if approval_status is not None:
                record.approval_status = (
                    approval_status
                )

            if recovery_status is not None:
                record.recovery_status = (
                    recovery_status
                )

            repository.update(record)

        finally:
            db.close()

    # =========================================================
    # Remediation
    # =========================================================

    def _build_remediation_request(
        self,
        incident: Incident,
        workflow: IncidentWorkflowResult,
    ) -> RemediationRequest:
        """
        Convert the AI remediation proposal into a validated
        application-level remediation request.
        """

        action = self._validate_remediation_action(
            workflow.analysis.remediation.action
        )

        return RemediationRequest(
            action=action,
            service=incident.service,
            namespace=incident.namespace,
            reason=workflow.analysis.root_cause,
        )

    # =========================================================
    # Incident Processing
    # =========================================================

    def process_incident(
        self,
        incident: Incident,
    ) -> IncidentWorkflowResult:
        """
        Process a newly detected incident.

        The incident is investigated once.

        Approval does not cause the investigation or LLM
        analysis to run again.
        """

        lifecycle = self._get_or_create_lifecycle(
            incident
        )

        try:
            # -------------------------------------------------
            # DETECTED -> INVESTIGATING
            # -------------------------------------------------

            lifecycle.transition(
                "INVESTIGATING",
                "Incident investigation started.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
            )

            # -------------------------------------------------
            # Investigation + AI analysis
            # -------------------------------------------------

            analysis = (
                self.investigation_agent.investigate(
                    incident
                )
            )

            # -------------------------------------------------
            # INVESTIGATING -> ANALYZED
            # -------------------------------------------------

            lifecycle.transition(
                "ANALYZED",
                "Incident investigation and root-cause analysis completed.",
            )

            workflow = IncidentWorkflowResult(
                stage="analysis",
                incident=incident.service,
                analysis=analysis,
                risk_decision=None,
                approval_required=False,
                remediation_executed=False,
                recovery_status=None,
            )

            # -------------------------------------------------
            # Build remediation request
            # -------------------------------------------------

            remediation_request = (
                self._build_remediation_request(
                    incident=incident,
                    workflow=workflow,
                )
            )

            # -------------------------------------------------
            # Deterministic risk evaluation
            # -------------------------------------------------

            risk_decision = (
                self.remediation_agent.evaluate(
                    remediation_request
                )
            )

            approval_required = (
                risk_decision.requires_approval
            )

            workflow = IncidentWorkflowResult(
                stage=(
                    "approval_required"
                    if approval_required
                    else "remediation_evaluation"
                ),
                incident=incident.service,
                analysis=analysis,
                risk_decision=risk_decision,
                approval_required=approval_required,
                remediation_executed=False,
                recovery_status=None,
            )

            self._workflows[
                incident.incident_id
            ] = workflow

            self._remediation_requests[
                incident.incident_id
            ] = remediation_request

            # -------------------------------------------------
            # ANALYZED -> AWAITING_APPROVAL
            # -------------------------------------------------

            if approval_required:
                lifecycle.transition(
                    "AWAITING_APPROVAL",
                    "Remediation requires explicit human approval.",
                )

                self._persist_incident(
                    incident=incident,
                    lifecycle=lifecycle,
                    workflow=workflow,
                    approval_status="PENDING",
                )

                return workflow

            # -------------------------------------------------
            # Future low-risk automatic remediation path
            # -------------------------------------------------

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
                approval_status="NOT_REQUIRED",
            )

            return workflow

        except Exception as exc:
            try:
                lifecycle.transition(
                    "FAILED",
                    f"Incident workflow failed: {exc}",
                )

                self._persist_incident(
                    incident=incident,
                    lifecycle=lifecycle,
                    workflow=self._workflows.get(
                        incident.incident_id
                    ),
                    approval_status="FAILED",
                    recovery_status="FAILED",
                )

            except Exception:
                pass

            raise

    # =========================================================
    # Approval + Execution
    # =========================================================

    def approve_and_execute(
        self,
        incident: Incident,
        approval: RemediationApproval,
    ) -> dict[str, object]:
        """
        Approve or reject a pending remediation.

        The incident is NOT re-analyzed during approval.
        The previously generated workflow and remediation
        request are reused.

        Persisted workflow state can also be used after an
        orchestrator process restart.
        """

        incident_id = incident.incident_id

        lifecycle = self._lifecycle_managers.get(
            incident_id
        )

        if lifecycle is None:
            raise KeyError(
                f"No lifecycle found for incident: {incident_id}"
            )

        if lifecycle.state != "AWAITING_APPROVAL":
            raise ValueError(
                "Incident is not awaiting approval."
            )

        workflow = self._workflows.get(
            incident_id
        )

        if workflow is None:
            raise KeyError(
                f"No workflow found for incident: {incident_id}"
            )

        remediation_request = (
            self._remediation_requests.get(
                incident_id
            )
        )

        if remediation_request is None:
            raise KeyError(
                f"No remediation request found for incident: {incident_id}"
            )

        # =====================================================
        # REJECTED APPROVAL
        # =====================================================

        if not approval.approved:
            lifecycle.transition(
                "REJECTED",
                "Human approval rejected the remediation.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
                approval_status="REJECTED",
                recovery_status=None,
            )

            return {
                "success": False,
                "status": "REJECTED",
                "incident_id": incident_id,
                "state": lifecycle.state,
                "approved": False,
                "remediation_executed": False,
                "recovery_status": None,
            }

        # =====================================================
        # APPROVED
        # =====================================================

        lifecycle.transition(
            "APPROVED",
            "Human approval granted for remediation.",
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=workflow,
            approval_status="APPROVED",
        )

        # =====================================================
        # APPROVED -> EXECUTING
        # =====================================================

        lifecycle.transition(
            "EXECUTING",
            "Approved remediation execution started.",
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=workflow,
            approval_status="APPROVED",
        )

        try:
            execution_result = (
                self.remediation_agent.execute(
                    request=remediation_request,
                    approved=True,
                )
            )

            # =================================================
            # Remediation execution failed
            # =================================================

            if not execution_result.get(
                "success",
                False,
            ):
                lifecycle.transition(
                    "FAILED",
                    "Remediation execution was not successful.",
                )

                self._persist_incident(
                    incident=incident,
                    lifecycle=lifecycle,
                    workflow=workflow,
                    approval_status="APPROVED",
                    recovery_status="FAILED",
                )

                return {
                    "success": False,
                    "status": "FAILED",
                    "incident_id": incident_id,
                    "state": lifecycle.state,
                    "approved": True,
                    "remediation_executed": False,
                    "execution": execution_result,
                    "recovery_status": "FAILED",
                }

            # =================================================
            # EXECUTING -> VERIFYING
            # =================================================

            lifecycle.transition(
                "VERIFYING",
                "Remediation execution completed. Recovery verification started.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
                approval_status="APPROVED",
            )

            # =================================================
            # Recovery verification
            # =================================================

            recovery_result = (
                self.remediation_agent.verify(
                    service=remediation_request.service,
                    namespace=remediation_request.namespace,
                )
            )

            if isinstance(
                recovery_result,
                dict,
            ):
                recovery_data = recovery_result.get(
                    "data",
                    recovery_result,
                )

                recovery_status = recovery_data.get(
                    "recovery_status",
                    recovery_data.get(
                        "status",
                        "NOT_RECOVERED",
                    ),
                )

            else:
                recovery_status = str(
                    recovery_result
                )

            # =================================================
            # Recovery successful
            # =================================================

            if recovery_status == "RECOVERED":
                lifecycle.transition(
                    "RECOVERED",
                    "Service recovered successfully after remediation.",
                )

                self._persist_incident(
                    incident=incident,
                    lifecycle=lifecycle,
                    workflow=workflow,
                    approval_status="APPROVED",
                    recovery_status="RECOVERED",
                )

                return {
                    "success": True,
                    "status": "RECOVERED",
                    "incident_id": incident_id,
                    "state": lifecycle.state,
                    "approved": True,
                    "remediation_executed": True,
                    "execution": execution_result,
                    "recovery_status": "RECOVERED",
                    "verification": recovery_result,
                }

            # =================================================
            # Remediation executed but recovery failed
            # =================================================

            lifecycle.transition(
                "FAILED",
                "Remediation completed but service did not recover.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
                approval_status="APPROVED",
                recovery_status=recovery_status,
            )

            return {
                "success": False,
                "status": recovery_status,
                "incident_id": incident_id,
                "state": lifecycle.state,
                "approved": True,
                "remediation_executed": True,
                "execution": execution_result,
                "recovery_status": recovery_status,
                "verification": recovery_result,
            }

        except Exception as exc:
            lifecycle.transition(
                "FAILED",
                f"Remediation execution failed: {exc}",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
                approval_status="APPROVED",
                recovery_status="FAILED",
            )

            raise
