import ast
import time
from typing import Any

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


def _load_kubernetes_config() -> client.CoreV1Api:
    """
    Load the user's Kubernetes configuration and return
    a CoreV1Api client.
    """

    try:
        config.load_kube_config()
    except ConfigException as error:
        raise RuntimeError(
            "Could not load Kubernetes configuration. "
            "Make sure kubectl is configured correctly."
        ) from error

    return client.CoreV1Api()


def _load_kubernetes_apps_client() -> client.AppsV1Api:
    """
    Load the user's Kubernetes configuration and return
    an AppsV1Api client.
    """

    try:
        config.load_kube_config()
    except ConfigException as error:
        raise RuntimeError(
            "Could not load Kubernetes configuration. "
            "Make sure kubectl is configured correctly."
        ) from error

    return client.AppsV1Api()


def _find_pod(
    api: client.CoreV1Api,
    service: str,
    namespace: str,
):
    """
    Find the first pod belonging to a service using
    the app=<service> label.
    """

    pods = api.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"app={service}",
    )

    if not pods.items:
        return None

    return pods.items[0]


def _normalize_logs(
    logs: Any,
) -> list[str]:
    """
    Normalize Kubernetes log output into clean text lines.

    Handles:
    - normal strings
    - bytes
    - strings containing a Python bytes representation
    """

    if isinstance(logs, bytes):
        text = logs.decode(
            "utf-8",
            errors="replace",
        )

    elif isinstance(logs, str):
        text = logs

        stripped = text.strip()

        if (
            len(stripped) >= 3
            and stripped.startswith(
                ("b'", 'b"')
            )
            and stripped.endswith(
                ("'", '"')
            )
        ):
            try:
                decoded = ast.literal_eval(
                    stripped
                )

                if isinstance(decoded, bytes):
                    text = decoded.decode(
                        "utf-8",
                        errors="replace",
                    )

            except (ValueError, SyntaxError):
                pass

    else:
        text = str(logs)

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _get_pod_state(
    pod,
) -> dict[str, Any]:
    """
    Extract normalized runtime state from a Kubernetes pod.
    """

    container_status = "Unknown"
    restart_count = 0
    reason = None

    if pod.status.container_statuses:
        container = pod.status.container_statuses[0]

        restart_count = (
            container.restart_count or 0
        )

        if container.state:
            if container.state.running:
                container_status = "Running"

            elif container.state.waiting:
                container_status = "Waiting"
                reason = (
                    container.state.waiting.reason
                )

            elif container.state.terminated:
                container_status = "Terminated"
                reason = (
                    container.state.terminated.reason
                )

    ready = False

    if pod.status.conditions:
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                ready = (
                    condition.status == "True"
                )
                break

    return {
        "pod": pod.metadata.name,
        "phase": pod.status.phase,
        "ready": ready,
        "restart_count": restart_count,
        "container_status": container_status,
        "reason": reason,
    }


def _get_application_log_health(
    logs: list[str],
) -> dict[str, Any]:
    """
    Determine whether recent application logs indicate
    an application-level failure.

    This is intentionally conservative.

    Known failure indicators include:
    - ERROR
    - FATAL
    - Traceback
    - Exception
    - failed startup
    - startup failed
    - connection refused
    - CrashLoopBackOff
    """

    failure_patterns = (
        "ERROR",
        "FATAL",
        "Traceback",
        "Exception",
        "failed startup",
        "startup failed",
        "connection refused",
        "CrashLoopBackOff",
    )

    matched_lines = []

    for line in logs:
        normalized = line.lower()

        if any(
            pattern.lower() in normalized
            for pattern in failure_patterns
        ):
            matched_lines.append(line)

    healthy = len(matched_lines) == 0

    return {
        "healthy": healthy,
        "failure_indicators": matched_lines,
    }


def _get_pod_events(
    api: client.CoreV1Api,
    pod_name: str,
    namespace: str,
) -> list[dict[str, str]]:
    """
    Retrieve events associated with a specific pod.
    """

    events = api.list_namespaced_event(
        namespace=namespace,
    )

    pod_events = []

    for event in events.items:
        involved_object = event.involved_object

        if (
            involved_object
            and involved_object.kind == "Pod"
            and involved_object.name == pod_name
        ):
            pod_events.append(
                {
                    "type": (
                        event.type
                        or "Normal"
                    ),
                    "reason": (
                        event.reason
                        or "Unknown"
                    ),
                    "message": (
                        event.message
                        or ""
                    ),
                }
            )

    return pod_events


def _get_warning_events(
    events: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Return Warning events only.
    """

    return [
        event
        for event in events
        if event["type"] == "Warning"
    ]


def get_pod_status(
    service: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """
    Read-only Kubernetes pod status tool.

    Finds a pod using the app=<service> label and returns
    normalized status information.
    """

    try:
        api = _load_kubernetes_config()

        pod = _find_pod(
            api=api,
            service=service,
            namespace=namespace,
        )

        if pod is None:
            return {
                "success": False,
                "service": service,
                "namespace": namespace,
                "error": (
                    f"No pod found for service "
                    f"'{service}'."
                ),
            }

        state = _get_pod_state(
            pod
        )

        return {
            "success": True,
            "data": {
                "service": service,
                "namespace": namespace,
                **state,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "error": str(error),
        }


def get_pod_logs(
    service: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """
    Read-only Kubernetes pod logs tool.

    Retrieves recent logs and normalizes them into
    individual clean text lines.
    """

    try:
        api = _load_kubernetes_config()

        pod = _find_pod(
            api=api,
            service=service,
            namespace=namespace,
        )

        if pod is None:
            return {
                "success": False,
                "service": service,
                "namespace": namespace,
                "error": (
                    f"No pod found for service "
                    f"'{service}'."
                ),
            }

        logs = api.read_namespaced_pod_log(
            name=pod.metadata.name,
            namespace=namespace,
            tail_lines=100,
        )

        log_lines = _normalize_logs(
            logs
        )

        return {
            "success": True,
            "data": {
                "service": service,
                "namespace": namespace,
                "logs": log_lines,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "error": str(error),
        }


def get_kubernetes_events(
    service: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """
    Read-only Kubernetes events tool.

    Retrieves events associated with the pod belonging
    to the specified service.
    """

    try:
        api = _load_kubernetes_config()

        pod = _find_pod(
            api=api,
            service=service,
            namespace=namespace,
        )

        if pod is None:
            return {
                "success": False,
                "service": service,
                "namespace": namespace,
                "error": (
                    f"No pod found for service "
                    f"'{service}'."
                ),
            }

        pod_events = _get_pod_events(
            api=api,
            pod_name=pod.metadata.name,
            namespace=namespace,
        )

        return {
            "success": True,
            "data": {
                "service": service,
                "namespace": namespace,
                "events": pod_events,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "error": str(error),
        }


def verify_deployment(
    service: str,
    namespace: str = "default",
    stability_seconds: int = 15,
    check_interval_seconds: int = 5,
) -> dict[str, Any]:
    """
    Perform application-aware Kubernetes recovery verification.

    Verification checks:

    1. Deployment rollout state
    2. Desired / updated / available / ready replicas
    3. Pod readiness
    4. Container runtime state
    5. Restart count
    6. Kubernetes Warning events
    7. Recent application logs
    8. Stability over a configurable time window

    The deployment is considered RECOVERED only when all
    required health conditions remain satisfied throughout
    the stability window.

    This function is read-only.
    """

    try:
        deployment_api = _load_kubernetes_apps_client()
        pod_api = client.CoreV1Api()

        deployment = (
            deployment_api.read_namespaced_deployment(
                name=service,
                namespace=namespace,
            )
        )

        desired_replicas = (
            deployment.spec.replicas or 0
        )

        updated_replicas = (
            deployment.status.updated_replicas or 0
        )

        available_replicas = (
            deployment.status.available_replicas
            or 0
        )

        ready_replicas = (
            deployment.status.ready_replicas
            or 0
        )

        observed_generation = (
            deployment.status.observed_generation
        )

        generation = deployment.metadata.generation

        rollout_complete = (
            observed_generation == generation
            and updated_replicas
            == desired_replicas
            and available_replicas
            == desired_replicas
            and ready_replicas
            == desired_replicas
        )

        pods = pod_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={service}",
        )

        if not pods.items:
            return {
                "success": True,
                "data": {
                    "service": service,
                    "namespace": namespace,
                    "recovery_status": "NOT_RECOVERED",
                    "recovery_reason": (
                        "No pods were found for the "
                        "deployment."
                    ),
                    "desired_replicas": desired_replicas,
                    "updated_replicas": updated_replicas,
                    "available_replicas": available_replicas,
                    "ready_replicas": ready_replicas,
                    "rollout_complete": rollout_complete,
                    "pods": [],
                    "application_health": {
                        "healthy": False,
                        "failure_indicators": [],
                    },
                    "warning_events": [],
                    "stability": {
                        "required_seconds": stability_seconds,
                        "observed_seconds": 0,
                        "stable": False,
                    },
                },
            }

        pod = pods.items[0]

        initial_state = _get_pod_state(
            pod
        )

        try:
            logs = pod_api.read_namespaced_pod_log(
                name=pod.metadata.name,
                namespace=namespace,
                tail_lines=100,
            )

            log_lines = _normalize_logs(
                logs
            )

        except Exception:
            log_lines = []

        application_health = (
            _get_application_log_health(
                log_lines
            )
        )

        pod_events = _get_pod_events(
            api=pod_api,
            pod_name=pod.metadata.name,
            namespace=namespace,
        )

        warning_events = _get_warning_events(
            pod_events
        )

        initial_kubernetes_health = (
            rollout_complete
            and initial_state["phase"] == "Running"
            and initial_state["ready"]
            and initial_state[
                "container_status"
            ]
            == "Running"
            and application_health["healthy"]
            and len(warning_events) == 0
        )

        stability_samples = [
            {
                "elapsed_seconds": 0,
                "pod": initial_state,
            }
        ]

        stable = initial_kubernetes_health

        start_time = time.monotonic()

        while (
            stable
            and (
                time.monotonic()
                - start_time
            )
            < stability_seconds
        ):
            sleep_seconds = min(
                check_interval_seconds,
                max(
                    0,
                    stability_seconds
                    - (
                        time.monotonic()
                        - start_time
                    ),
                ),
            )

            if sleep_seconds > 0:
                time.sleep(
                    sleep_seconds
                )

            current_pods = (
                pod_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"app={service}",
                )
            )

            if not current_pods.items:
                stable = False
                break

            current_pod = current_pods.items[0]

            current_state = _get_pod_state(
                current_pod
            )

            stability_samples.append(
                {
                    "elapsed_seconds": round(
                        time.monotonic()
                        - start_time,
                        2,
                    ),
                    "pod": current_state,
                }
            )

            if (
                current_pod.metadata.name
                != pod.metadata.name
            ):
                stable = False
                break

            if (
                current_state["phase"]
                != "Running"
                or not current_state["ready"]
                or current_state[
                    "container_status"
                ]
                != "Running"
            ):
                stable = False
                break

            if (
                current_state["restart_count"]
                != initial_state[
                    "restart_count"
                ]
            ):
                stable = False
                break

            try:
                current_logs = (
                    pod_api.read_namespaced_pod_log(
                        name=current_pod.metadata.name,
                        namespace=namespace,
                        tail_lines=100,
                    )
                )

                current_log_lines = (
                    _normalize_logs(
                        current_logs
                    )
                )

            except Exception:
                current_log_lines = []

            current_application_health = (
                _get_application_log_health(
                    current_log_lines
                )
            )

            if not current_application_health[
                "healthy"
            ]:
                stable = False
                application_health = (
                    current_application_health
                )
                break

            current_events = _get_pod_events(
                api=pod_api,
                pod_name=current_pod.metadata.name,
                namespace=namespace,
            )

            current_warning_events = (
                _get_warning_events(
                    current_events
                )
            )

            if current_warning_events:
                stable = False
                warning_events = (
                    current_warning_events
                )
                break

        observed_seconds = round(
            time.monotonic()
            - start_time,
            2,
        )

        recovery_status = (
            "RECOVERED"
            if (
                stable
                and initial_kubernetes_health
                and observed_seconds
                >= stability_seconds
            )
            else "NOT_RECOVERED"
        )

        if recovery_status == "RECOVERED":
            recovery_reason = (
                "Deployment rollout completed, the pod "
                "remained ready and running, restart count "
                "remained stable, no Kubernetes Warning "
                "events were detected, application logs "
                "showed no known failure indicators, and "
                "the service remained stable throughout "
                "the verification window."
            )
        else:
            reasons = []

            if not rollout_complete:
                reasons.append(
                    "deployment rollout is not complete"
                )

            if initial_state["phase"] != "Running":
                reasons.append(
                    "pod is not running"
                )

            if not initial_state["ready"]:
                reasons.append(
                    "pod is not ready"
                )

            if (
                initial_state["container_status"]
                != "Running"
            ):
                reasons.append(
                    "container is not running"
                )

            if not application_health["healthy"]:
                reasons.append(
                    "application logs contain "
                    "failure indicators"
                )

            if warning_events:
                reasons.append(
                    "Kubernetes Warning events "
                    "were detected"
                )

            if not stable:
                reasons.append(
                    "service did not remain stable "
                    "during the verification window"
                )

            recovery_reason = (
                "; ".join(reasons)
                if reasons
                else (
                    "Recovery verification failed."
                )
            )

        pod_result = {
            **initial_state,
        }

        return {
            "success": True,
            "data": {
                "service": service,
                "namespace": namespace,
                "recovery_status": recovery_status,
                "recovery_reason": recovery_reason,
                "desired_replicas": desired_replicas,
                "updated_replicas": updated_replicas,
                "available_replicas": available_replicas,
                "ready_replicas": ready_replicas,
                "rollout_complete": rollout_complete,
                "pods": [
                    pod_result
                ],
                "application_health": (
                    application_health
                ),
                "warning_events": warning_events,
                "stability": {
                    "required_seconds": stability_seconds,
                    "observed_seconds": observed_seconds,
                    "stable": stable,
                    "samples": stability_samples,
                },
            },
        }

    except Exception as error:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "error": str(error),
        }
