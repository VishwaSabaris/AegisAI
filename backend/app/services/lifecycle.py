from backend.app.models.lifecycle import (
    IncidentLifecycle,
    IncidentState,
)
from backend.app.services.metrics import (
    INCIDENTS_BY_STATE,
)


class IncidentLifecycleManager:
    """
    Owns and validates the lifecycle state of one incident.

    Lifecycle manager construction itself does not modify metrics.
    New incidents explicitly call mark_detected(), while persisted
    incidents call restore() with their database state.
    """

    _TRANSITIONS: dict[
        IncidentState,
        set[IncidentState],
    ] = {
        "DETECTED": {
            "INVESTIGATING",
            "FAILED",
        },
        "INVESTIGATING": {
            "ANALYZED",
            "FAILED",
        },
        "ANALYZED": {
            "AWAITING_APPROVAL",
            "EXECUTING",
            "FAILED",
        },
        "AWAITING_APPROVAL": {
            "APPROVED",
            "REJECTED",
            "FAILED",
        },
        "APPROVED": {
            "EXECUTING",
            "FAILED",
        },
        "REJECTED": set(),
        "EXECUTING": {
            "VERIFYING",
            "FAILED",
        },
        "VERIFYING": {
            "RECOVERED",
            "FAILED",
        },
        "RECOVERED": set(),
        "FAILED": set(),
        "COMPLETED": set(),
    }

    def __init__(
        self,
        incident_id: str,
        service: str,
        namespace: str = "default",
    ) -> None:
        self._lifecycle = IncidentLifecycle(
            incident_id=incident_id,
            service=service,
            namespace=namespace,
            state="DETECTED",
            previous_state=None,
            message="Incident detected.",
        )

    @property
    def lifecycle(self) -> IncidentLifecycle:
        """
        Return the current lifecycle object.
        """

        return self._lifecycle

    @property
    def state(self) -> IncidentState:
        """
        Return the current lifecycle state.
        """

        return self._lifecycle.state

    def mark_detected(self) -> IncidentLifecycle:
        """
        Register a newly created incident as DETECTED.

        This is intentionally separate from __init__ so that creating
        a lifecycle manager during PostgreSQL rehydration does not
        incorrectly increment the DETECTED metric.
        """

        INCIDENTS_BY_STATE.labels(
            state="DETECTED"
        ).inc()

        return self.lifecycle

    def restore(
        self,
        lifecycle: IncidentLifecycle,
    ) -> IncidentLifecycle:
        """
        Restore a persisted lifecycle state.

        Only the persisted state is added to the lifecycle gauge.
        No DETECTED increment is performed during restoration.
        """

        self._lifecycle = lifecycle

        INCIDENTS_BY_STATE.labels(
            state=lifecycle.state
        ).inc()

        return self.lifecycle

    def transition(
        self,
        new_state: IncidentState,
        message: str,
    ) -> IncidentLifecycle:
        """
        Transition the incident to a validated next state.
        """

        current_state = self._lifecycle.state

        allowed_states = self._TRANSITIONS.get(
            current_state,
            set(),
        )

        if new_state not in allowed_states:
            raise ValueError(
                f"Invalid lifecycle transition: "
                f"{current_state} -> {new_state}"
            )

        self._lifecycle = IncidentLifecycle(
            incident_id=self._lifecycle.incident_id,
            service=self._lifecycle.service,
            namespace=self._lifecycle.namespace,
            state=new_state,
            previous_state=current_state,
            message=message,
        )

        INCIDENTS_BY_STATE.labels(
            state=current_state
        ).dec()

        INCIDENTS_BY_STATE.labels(
            state=new_state
        ).inc()

        return self.lifecycle

    @classmethod
    def allowed_transitions(
        cls,
        state: IncidentState,
    ) -> list[IncidentState]:
        """
        Return the states allowed from the supplied state.
        """

        return list(
            cls._TRANSITIONS.get(
                state,
                set(),
            )
        )
