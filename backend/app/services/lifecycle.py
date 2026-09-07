from backend.app.models.lifecycle import (
    IncidentLifecycle,
    IncidentState,
)


class IncidentLifecycleManager:
    """
    Deterministic state machine for AegisAI incidents.

    The LLM cannot directly change lifecycle state.
    """

    _TRANSITIONS: dict[
        IncidentState,
        set[IncidentState],
    ] = {
        "DETECTED": {
            "INVESTIGATING",
        },
        "INVESTIGATING": {
            "ANALYZED",
            "FAILED",
        },
        "ANALYZED": {
            "AWAITING_APPROVAL",
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
        "REJECTED": {
        },
        "EXECUTING": {
            "VERIFYING",
            "FAILED",
        },
        "VERIFYING": {
            "RECOVERED",
            "FAILED",
        },
        "RECOVERED": {
        },
        "FAILED": {
        },
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
        Return the current lifecycle state.
        """

        return self._lifecycle.model_copy(
            deep=True
        )

    @property
    def state(self) -> IncidentState:
        """
        Return the current state.
        """

        return self._lifecycle.state

    def transition(
        self,
        new_state: IncidentState,
        message: str,
    ) -> IncidentLifecycle:
        """
        Perform a validated lifecycle transition.
        """

        current_state = self._lifecycle.state

        allowed_states = self._TRANSITIONS.get(
            current_state,
            set(),
        )

        if new_state not in allowed_states:
            raise ValueError(
                f"Invalid incident lifecycle transition: "
                f"{current_state} -> {new_state}. "
                f"Allowed transitions: "
                f"{sorted(allowed_states)}"
            )

        self._lifecycle = IncidentLifecycle(
            incident_id=self._lifecycle.incident_id,
            service=self._lifecycle.service,
            namespace=self._lifecycle.namespace,
            state=new_state,
            previous_state=current_state,
            message=message,
        )

        return self.lifecycle

    @classmethod
    def allowed_transitions(
        cls,
        state: IncidentState,
    ) -> list[IncidentState]:
        """
        Return valid next states for a given state.
        """

        return sorted(
            cls._TRANSITIONS.get(
                state,
                set(),
            )
        )
