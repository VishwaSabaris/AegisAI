from backend.app.tools.kubernetes import get_pod_status


def main():
    print("=" * 60)
    print("AegisAI - Real Kubernetes Tool Test")
    print("=" * 60)

    print("\nQuerying real Kubernetes cluster...")

    result = get_pod_status(
        service="payment-service",
        namespace="aegis-demo",
    )

    print("\nTool result:")
    print("-" * 60)
    print(result)
    print("-" * 60)

    assert result["success"] is True

    data = result["data"]

    assert data["service"] == "payment-service"
    assert data["namespace"] == "aegis-demo"

    assert data["pod"].startswith(
        "payment-service-"
    )

    assert data["ready"] is False
    assert data["restart_count"] >= 1

    assert data["phase"] in [
        "Running",
        "Pending",
        "Succeeded",
        "Failed",
        "Unknown",
    ]

    print("\nReal Kubernetes data validated successfully.")

    print("\nObserved:")
    print(f"Pod: {data['pod']}")
    print(f"Phase: {data['phase']}")
    print(f"Ready: {data['ready']}")
    print(f"Restart count: {data['restart_count']}")
    print(f"Reason: {data['reason']}")
    print(f"Container status: {data['container_status']}")

    print("\nAll assertions passed.")
    print("Real get_pod_status() tool is working correctly.")


if __name__ == "__main__":
    main()
