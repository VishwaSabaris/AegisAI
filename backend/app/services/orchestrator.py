import time
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
from backend.app.services.metrics import (
    INCIDENTS_TOTAL,
    INCIDENT_PROCESSING_DURATION_SECONDS,
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

    IMPORTANT SAFETY BOUNDARY:

    The LLM's remediation risk and approval recommendation are
    advisory only.

    The deterministic RemediationRiskPolicy is authoritative
    for risk classification and approval requirements.
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

        Deterministic risk policy is re-evaluated during rehydration
        so persisted LLM approval values cannot override the current
        application safety policy.
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

        The persisted lifecycle state is restored directly.

        When an analysis exists, the remediation action is
        reconstructed and passed through the deterministic
        risk policy again.

        The deterministic risk policy is authoritative for:
        - remediation risk
        - approval requirement

        Persisted LLM-generated values are never trusted for
        those safety decisions.
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

        lifecycle.restore(
            IncidentLifecycle(
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
        )

        self._lifecycle_managers[
            incident.incident_id
        ] = lifecycle

        if (
            record.severity is None
            or record.root_cause is None
            or record.confidence is None
            or record.remediation_action is None
        ):
            return

        action = self._validate_remediation_action(
            record.remediation_action
        )

        remediation_request = RemediationRequest(
            action=action,
            service=incident.service,
            namespace=incident.namespace,
            reason=record.root_cause,
        )

        self._remediation_requests[
            incident.incident_id
        ] = remediation_request

        risk_decision = (
            self.remediation_agent.risk_policy.evaluate(
                remediation_request
            )
        )

        remediation = RemediationProposal(
            action=action,
            risk=risk_decision.risk,
            requires_approval=(
                risk_decision.requires_approval
            ),
        )

        persisted_evidence = (
            record.evidence
            if record.evidence is not None
            else []
        )

        persisted_next_checks = (
            record.next_checks
            if record.next_checks is not None
            else []
        )

        analysis = IncidentAnalysis(
            severity=cast(
                str,
                record.severity,
            ),
            root_cause=record.root_cause,
            confidence=record.confidence,
            evidence=list(persisted_evidence),
            next_checks=list(persisted_next_checks),
            remediation=remediation,
        )

        workflow_stage = self._workflow_stage_from_state(
            persisted_state
        )

        terminal_state = persisted_state in {
            "RECOVERED",
            "FAILED",
            "REJECTED",
        }

        remediation_executed = (
            record.approval_status == "APPROVED"
            and record.recovery_status is not None
            and persisted_state in {
                "RECOVERED",
                "FAILED",
            }
        )

        workflow = IncidentWorkflowResult(
            stage=workflow_stage,
            incident=incident.service,
            analysis=analysis,
            risk_decision=risk_decision,
            approval_required=(
                False
                if terminal_state
                else risk_decision.requires_approval
            ),
            remediation_executed=remediation_executed,
            recovery_status=record.recovery_status,
        )

        self._workflows[
            incident.incident_id
        ] = workflow

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
            "RECOVERED",
            "FAILED",
            "REJECTED",
        }:
            return "completed"

        if state in {
            "APPROVED",
            "EXECUTING",
            "VERIFYING",
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

        Newly created incidents are explicitly registered as
        DETECTED so lifecycle metrics do not confuse manager
        construction during PostgreSQL rehydration with new
        incident detection.
        """

        if incident.incident_id not in self._lifecycle_managers:
            lifecycle = IncidentLifecycleManager(
                incident_id=incident.incident_id,
                service=incident.service,
                namespace=incident.namespace,
            )

            lifecycle.mark_detected()

            self._lifecycle_managers[
                incident.incident_id
            ] = lifecycle

        return self._lifecycle_managers[
            incident.incident_id
        ]

    def register_incident(
        self,
        incident: Incident,
        grafana_fingerprint: str | None = None,
    ) -> IncidentLifecycle:
        """
        Register a newly detected incident without starting
        investigation.

        This method is intentionally lightweight so webhook
        handlers can persist the incident and return quickly.

        The expensive investigation and LLM processing are
        performed later by process_incident().
        """

        lifecycle = self._get_or_create_lifecycle(
            incident
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            grafana_fingerprint=grafana_fingerprint,
        )

        return lifecycle.lifecycle

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

    def get_workflow(
        self,
        incident_id: str,
    ) -> IncidentWorkflowResult:
        """
        Return the current workflow state for an incident.

        Workflow state is restored from PostgreSQL during
        orchestrator initialization and then maintained in
        memory during the process lifetime.
        """

        workflow = self._workflows.get(
            incident_id
        )

        if workflow is None:
            raise KeyError(
                f"No workflow found for incident: {incident_id}"
            )

        return workflow

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
        grafana_fingerprint: str | None = None,
    ) -> None:
        """
        Persist the current incident lifecycle and workflow state.

        The analysis evidence and next checks are persisted so
        that they can be restored after an orchestrator restart.

        When a new incident originates from Grafana, its alert
        fingerprint is persisted so repeated Grafana notifications
        can be identified as the same incident.
        """

        db = SessionLocal()

        try:
            repository = IncidentRepository(db)

            record = repository.get_by_incident_id(
                incident.incident_id
            )

            if record is None:
                record = repository.create(
                    incident,
                    grafana_fingerprint=grafana_fingerprint,
                )

            lifecycle_state = lifecycle.lifecycle

            record.lifecycle_state = (
                lifecycle_state.state
            )

            record.previous_lifecycle_state = (
                lifecycle_state.previous_state
            )

            record.lifecycle_message = (
                lifecycle_state.message
            )

            if workflow is not None:
                analysis = workflow.analysis

                record.severity = analysis.severity
                record.root_cause = analysis.root_cause
                record.confidence = analysis.confidence
                record.evidence = analysis.evidence
                record.next_checks = analysis.next_checks

                record.remediation_action = (
                    analysis.remediation.action
                )

                record.remediation_risk = (
                    analysis.remediation.risk
                )

                record.requires_approval = (
                    analysis.remediation.requires_approval
                )

            if approval_status is not None:
                record.approval_status = approval_status

            if recovery_status is not None:
                record.recovery_status = recovery_status

            repository.update(record)

        finally:
            db.close()

    # =========================================================
    # Remediation Request
    # =========================================================

    def _build_remediation_request(
        self,
        incident: Incident,
        analysis: IncidentAnalysis,
    ) -> RemediationRequest:
        """
        Build a remediation request from the validated analysis.

        The action is validated against the application-level
        allowlist before being passed to the risk policy.
        """

        action = self._validate_remediation_action(
            analysis.remediation.action
        )

        return RemediationRequest(
            action=action,
            service=incident.service,
            namespace=incident.namespace,
            reason=analysis.root_cause,
        )

    # =========================================================
    # Incident Processing
    # =========================================================

    def process_incident(
        self,
        incident: Incident,
        grafana_fingerprint: str | None = None,
    ) -> IncidentWorkflowResult:
        """
        Process a new incident through investigation,
        analysis, risk evaluation, and approval gating.

        Infrastructure-changing remediation is never executed
        automatically when approval is required.

        When provided, the Grafana alert fingerprint is persisted
        with the incident for idempotent webhook processing.
        """

        start_time = time.perf_counter()

        try:
            lifecycle = self._get_or_create_lifecycle(
                incident
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                grafana_fingerprint=grafana_fingerprint,
            )

            lifecycle.transition(
                "INVESTIGATING",
                message="Investigation started.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
            )

            analysis = (
                self.investigation_agent.investigate(
                    incident
                )
            )

            INCIDENTS_TOTAL.labels(
                service=incident.service,
                severity=analysis.severity,
            ).inc()

            lifecycle.transition(
                "ANALYZED",
                message="Investigation completed.",
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
            )

            remediation_request = (
                self._build_remediation_request(
                    incident=incident,
                    analysis=analysis,
                )
            )

            self._remediation_requests[
                incident.incident_id
            ] = remediation_request

            risk_decision = (
                self.remediation_agent.evaluate(
                    remediation_request
                )
            )

            analysis = analysis.model_copy(
                update={
                    "remediation": RemediationProposal(
                        action=remediation_request.action,
                        risk=risk_decision.risk,
                        requires_approval=(
                            risk_decision.requires_approval
                        ),
                    )
                }
            )

            workflow = IncidentWorkflowResult(
                stage="remediation_evaluation",
                incident=incident.service,
                analysis=analysis,
                risk_decision=risk_decision,
                approval_required=(
                    risk_decision.requires_approval
                ),
                remediation_executed=False,
                recovery_status=None,
            )

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
            )

            if risk_decision.requires_approval:
                lifecycle.transition(
                    "AWAITING_APPROVAL",
                    message=(
                        "Remediation requires explicit "
                        "human approval."
                    ),
                )

                workflow = workflow.model_copy(
                    update={
                        "stage": "approval_required",
                        "approval_required": True,
                    }
                )

                self._workflows[
                    incident.incident_id
                ] = workflow

                self._persist_incident(
                    incident=incident,
                    lifecycle=lifecycle,
                    workflow=workflow,
                    approval_status="PENDING",
                )

                return workflow

            self._workflows[
                incident.incident_id
            ] = workflow

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=workflow,
            )

            return workflow

        finally:
            elapsed = time.perf_counter() - start_time
            INCIDENT_PROCESSING_DURATION_SECONDS.observe(
                elapsed
            )

    # =========================================================
    # Approval / Execution
    # =========================================================

    def approve_and_execute(
        self,
        incident: Incident,
        approval: RemediationApproval,
    ) -> dict:
        """
        Apply a human approval decision and execute remediation
        when approved.

        Existing analysis and remediation request are reused.
        The incident is not sent through investigation again.
        """

        incident_id = incident.incident_id

        lifecycle = self._lifecycle_managers.get(
            incident_id
        )

        if lifecycle is None:
            raise KeyError(
                f"No lifecycle found for incident: {incident_id}"
            )

        workflow = self._workflows.get(
            incident_id
        )

        if workflow is None:
            raise KeyError(
                f"No workflow found for incident: {incident_id}"
            )

        if lifecycle.lifecycle.state != "AWAITING_APPROVAL":
            raise ValueError(
                "Incident is not awaiting approval."
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

        # -----------------------------------------------------
        # Rejected approval
        # -----------------------------------------------------

        if not approval.approved:
            lifecycle.transition(
                "REJECTED",
                message=(
                    "Remediation rejected by human approver."
                ),
            )

            rejected_workflow = workflow.model_copy(
                update={
                    "stage": "completed",
                    "approval_required": False,
                    "remediation_executed": False,
                    "recovery_status": None,
                }
            )

            self._workflows[
                incident_id
            ] = rejected_workflow

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=rejected_workflow,
                approval_status="REJECTED",
            )

            return {
                "success": False,
                "status": "REJECTED",
                "incident_id": incident_id,
                "approval": {
                    "approved": False,
                    "approved_by": approval.approved_by,
                    "comment": approval.comment,
                },
                "remediation_executed": False,
                "recovery_status": None,
                "workflow": (
                    rejected_workflow.model_dump()
                ),
                "lifecycle": (
                    lifecycle.lifecycle.model_dump()
                ),
            }

        # -----------------------------------------------------
        # Approval accepted
        # -----------------------------------------------------

        lifecycle.transition(
            "APPROVED",
            message=(
                "Remediation approved by human approver."
            ),
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=workflow,
            approval_status="APPROVED",
        )

        lifecycle.transition(
            "EXECUTING",
            message=(
                "Approved remediation execution started."
            ),
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=workflow,
            approval_status="APPROVED",
        )

        # -----------------------------------------------------
        # Execute remediation
        # -----------------------------------------------------

        execution_result = (
            self.remediation_agent.execute(
                request=remediation_request,
                approved=True,
            )
        )

        if not execution_result.get("success"):
            lifecycle.transition(
                "FAILED",
                message=(
                    "Approved remediation execution failed."
                ),
            )

            failed_workflow = workflow.model_copy(
                update={
                    "stage": "completed",
                    "approval_required": False,
                    "remediation_executed": False,
                    "recovery_status": "NOT_RECOVERED",
                }
            )

            self._workflows[
                incident_id
            ] = failed_workflow

            self._persist_incident(
                incident=incident,
                lifecycle=lifecycle,
                workflow=failed_workflow,
                approval_status="APPROVED",
                recovery_status="NOT_RECOVERED",
            )

            return {
                "success": False,
                "status": "FAILED",
                "incident_id": incident_id,
                "approval": {
                    "approved": True,
                    "approved_by": approval.approved_by,
                    "comment": approval.comment,
                },
                "remediation_executed": False,
                "recovery_status": "NOT_RECOVERED",
                "execution": execution_result,
                "workflow": (
                    failed_workflow.model_dump()
                ),
                "lifecycle": (
                    lifecycle.lifecycle.model_dump()
                ),
            }

        # -----------------------------------------------------
        # Verification
        # -----------------------------------------------------

        lifecycle.transition(
            "VERIFYING",
            message=(
                "Remediation executed. "
                "Verification started."
            ),
        )

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=workflow,
            approval_status="APPROVED",
        )

        verification_result = (
            self.remediation_agent.verify(
                service=incident.service,
                namespace=incident.namespace,
            )
        )

        # verify() returns:
        #
        # {
        #     "success": True,
        #     "data": {
        #         "recovery_status": "RECOVERED"
        #     }
        # }
        #
        # Therefore recovery_status must be extracted from
        # the nested "data" object.

        verification_data = (
            verification_result.get("data", {})
        )

        recovery_status = verification_data.get(
            "recovery_status"
        )

        # -----------------------------------------------------
        # Lifecycle outcome
        # -----------------------------------------------------

        if recovery_status == "RECOVERED":
            lifecycle.transition(
                "RECOVERED",
                message="Service recovered successfully.",
            )
        else:
            lifecycle.transition(
                "FAILED",
                message="Service did not recover.",
            )

        # -----------------------------------------------------
        # Final workflow state
        # -----------------------------------------------------

        final_workflow = workflow.model_copy(
            update={
                "stage": "completed",
                "approval_required": False,
                "remediation_executed": True,
                "recovery_status": recovery_status,
            }
        )

        self._workflows[
            incident_id
        ] = final_workflow

        self._persist_incident(
            incident=incident,
            lifecycle=lifecycle,
            workflow=final_workflow,
            approval_status="APPROVED",
            recovery_status=recovery_status,
        )

        # -----------------------------------------------------
        # Final API result
        # -----------------------------------------------------

        return {
            "success": recovery_status == "RECOVERED",
            "status": recovery_status,
            "incident_id": incident_id,
            "approval": {
                "approved": True,
                "approved_by": approval.approved_by,
                "comment": approval.comment,
            },
            "remediation_executed": True,
            "recovery_status": recovery_status,
            "execution": execution_result,
            "verification": verification_result,
            "workflow": (
                final_workflow.model_dump()
            ),
            "lifecycle": (
                lifecycle.lifecycle.model_dump()
            ),
        }
