from datetime import datetime, timezone
from typing import Any

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


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


def restart_deployment(
    service: str,
    namespace: str = "default",
    approved: bool = False,
) -> dict[str, Any]:
    """
    Restart a Kubernetes deployment.

    This is a write operation and requires explicit
    human approval.

    Kubernetes performs the restart when the pod template
    annotation changes.
    """

    if not approved:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "action": "restart_deployment",
            "error": (
                "Remediation blocked: explicit human "
                "approval is required before executing "
                "this action."
            ),
        }

    try:
        api = _load_kubernetes_apps_client()

        deployment = api.read_namespaced_deployment(
            name=service,
            namespace=namespace,
        )

        current_annotations = (
            deployment.spec.template.metadata.annotations
            or {}
        )

        annotations = dict(
            current_annotations
        )

        restart_timestamp = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        annotations[
            "aegisai.dev/restarted-at"
        ] = restart_timestamp

        patch_body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": annotations
                    }
                }
            }
        }

        api.patch_namespaced_deployment(
            name=service,
            namespace=namespace,
            body=patch_body,
        )

        return {
            "success": True,
            "service": service,
            "namespace": namespace,
            "action": "restart_deployment",
            "restart_timestamp": restart_timestamp,
            "message": (
                f"Deployment '{service}' restart "
                "requested successfully."
            ),
        }

    except Exception as error:
        return {
            "success": False,
            "service": service,
            "namespace": namespace,
            "action": "restart_deployment",
            "error": str(error),
        }
