import json
import time

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from backend.app.agents.remediation import RemediationAgent
from backend.app.models.remediation import RemediationRequest


SERVICE = "healthy-payment-service"
NAMESPACE = "aegis-demo"


def load_clients():
    """
    Load the local Kubernetes configuration and return
    CoreV1Api and AppsV1Api clients.
    """

    try:
        config.load_kube_config()
    except ConfigException as error:
        raise RuntimeError(
            "Could not load Kubernetes configuration."
        ) from error

    return client.CoreV1Api(), client.AppsV1Api()


def create_healthy_deployment() -> None:
    """
    Create a real healthy Kubernetes deployment for the
    positive recovery test.
    """

    core_api, apps_api = load_clients()

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=SERVICE,
            namespace=NAMESPACE,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(
                match_labels={
                    "app": SERVICE,
                }
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": SERVICE,
                    }
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=SERVICE,
                            image="python:3.12-alpine",
                            command=[
                                "python",
                                "-c",
                                (
                                    "import time\n"
                                    "print("
                                    "\"Starting healthy-payment-service\", "
                                    "flush=True"
                                    ")\n"
                                    "print("
                                    "\"Loading application configuration\", "
                                    "flush=True"
                                    ")\n"
                                    "print("
                                    "\"Application startup successful\", "
                                    "flush=True"
                                    ")\n"
                                    "print("
                                    "\"Payment service is healthy\", "
                                    "flush=True"
                                    ")\n"
                                    "while True:\n"
                                    "    time.sleep(60)\n"
                                ),
                            ],
                        )
                    ]
                ),
            ),
        ),
    )

    try:
        apps_api.delete_namespaced_deployment(
            name=SERVICE,
            namespace=NAMESPACE,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground"
            ),
        )

        print(
            f"Existing deployment '{SERVICE}' "
            "deleted."
        )

        time.sleep(2)

    except client.exceptions.ApiException as error:
        if error.status != 404:
            raise

    apps_api.create_namespaced_deployment(
        namespace=NAMESPACE,
        body=deployment,
    )

    print(
        f"Healthy deployment '{SERVICE}' created."
    )

    print(
        "\nWaiting for healthy deployment..."
    )

    for _ in range(30):
        deployment_status = (
            apps_api.read_namespaced_deployment(
                name=SERVICE,
                namespace=NAMESPACE,
            )
        )

        ready_replicas = (
            deployment_status.status.ready_replicas
            or 0
        )

        if ready_replicas == 1:
            print(
                "Healthy deployment is Ready."
            )
            return

        time.sleep(1)

    raise RuntimeError(
        "Healthy deployment did not become Ready "
        "within the expected time."
    )


def delete_healthy_deployment() -> None:
    """
    Remove the temporary positive-test deployment.
    """

    _, apps_api = load_clients()

    try:
        apps_api.delete_namespaced_deployment(
            name=SERVICE,
            namespace=NAMESPACE,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground"
            ),
        )

        print(
            f"\nTemporary deployment '{SERVICE}' "
            "deleted."
        )

    except client.exceptions.ApiException as error:
        if error.status != 404:
            raise


def main() -> None:
    print("=" * 60)
    print("AegisAI - Positive Recovery Test")
    print("=" * 60)

    create_healthy_deployment()

    agent = RemediationAgent()

    request = RemediationRequest(
        action="restart_deployment",
        service=SERVICE,
        namespace=NAMESPACE,
        reason=(
            "Healthy payment service is being restarted "
            "to verify successful recovery detection."
        ),
    )

    print("\nRemediation request:")
    print(
        json.dumps(
            request.model_dump(),
            indent=2,
        )
    )

    decision = agent.evaluate(
        request
    )

    print("\nRisk decision:")
    print(
        json.dumps(
            decision.model_dump(),
            indent=2,
        )
    )

    assert decision.action == "restart_deployment"
    assert decision.risk == "medium"
    assert decision.requires_approval is True
    assert decision.allowed is False

    print(
        "\nExecuting remediation with explicit approval..."
    )

    result = agent.execute(
        request,
        approved=True,
    )

    print("\nRemediation result:")
    print("-" * 60)
    print(result)
    print("-" * 60)

    assert result["success"] is True
    assert result["action"] == "restart_deployment"

    print(
        "\nKubernetes restart request accepted."
    )

    print(
        "\nWaiting for Kubernetes to process "
        "the deployment restart..."
    )

    time.sleep(5)

    print(
        "\nVerifying deployment recovery..."
    )

    verification = agent.verify(
        service=SERVICE,
        namespace=NAMESPACE,
    )

    print("\nVerification result:")
    print("-" * 60)
    print(
        json.dumps(
            verification,
            indent=2,
        )
    )
    print("-" * 60)

    assert verification["success"] is True

    data = verification["data"]

    print(
        f"\nRecovery status: "
        f"{data['recovery_status']}"
    )

    print(
        f"Recovery reason: "
        f"{data['recovery_reason']}"
    )

    print("\nApplication health:")
    print(
        json.dumps(
            data["application_health"],
            indent=2,
        )
    )

    print("\nStability:")
    print(
        json.dumps(
            data["stability"],
            indent=2,
        )
    )

    print("\nPods:")

    for pod in data["pods"]:
        print(
            f"  Pod: {pod['pod']}"
        )
        print(
            f"  Phase: {pod['phase']}"
        )
        print(
            f"  Ready: {pod['ready']}"
        )
        print(
            f"  Restarts: {pod['restart_count']}"
        )
        print(
            f"  Container: "
            f"{pod['container_status']}"
        )
        print(
            f"  Reason: {pod['reason']}"
        )

    print("\nExecution history:")
    print("-" * 60)

    history = agent.registry.get_execution_history()

    assert len(history) == 2

    for record in history:
        print(
            f"Tool: {record.tool_name}"
        )
        print(
            f"Arguments: {record.arguments}"
        )
        print(
            f"Success: {record.success}"
        )
        print(
            f"Duration: "
            f"{record.duration_ms:.2f} ms"
        )
        print(
            f"Error: {record.error}"
        )
        print("-" * 60)

    assert history[0].tool_name == (
        "restart_deployment"
    )

    assert history[0].success is True

    assert history[1].tool_name == (
        "verify_deployment"
    )

    assert history[1].success is True

    # The healthy test application should remain
    # running and stable throughout verification.
    assert (
        data["recovery_status"]
        == "RECOVERED"
    )

    assert (
        data["rollout_complete"]
        is True
    )

    assert (
        data["desired_replicas"]
        == 1
    )

    assert (
        data["updated_replicas"]
        == 1
    )

    assert (
        data["available_replicas"]
        == 1
    )

    assert (
        data["ready_replicas"]
        == 1
    )

    assert (
        data["application_health"]["healthy"]
        is True
    )

    assert (
        data["stability"]["stable"]
        is True
    )

    assert (
        data["stability"]["observed_seconds"]
        >= data["stability"]["required_seconds"]
    )

    assert (
        len(data["warning_events"])
        == 0
    )

    print(
        "\nRecovery result: RECOVERED"
    )

    print(
        "\nExpected behavior confirmed:"
    )

    print(
        "  Remediation execution: SUCCESS"
    )

    print(
        "  Application recovery: RECOVERED"
    )

    print(
        "\nThe healthy application remained "
        "stable throughout the verification window."
    )

    delete_healthy_deployment()

    print(
        "\nAll assertions passed."
    )


if __name__ == "__main__":
    main()
