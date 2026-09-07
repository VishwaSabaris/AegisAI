from backend.app.tools.kubernetes import get_pod_logs


def main():
    print("=" * 60)
    print("AegisAI - Real Kubernetes Logs Test")
    print("=" * 60)

    print("\nQuerying real Kubernetes pod logs...")

    result = get_pod_logs(
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

    assert isinstance(
        data["logs"],
        list,
    )

    assert len(data["logs"]) > 0

    combined_logs = "\n".join(
        data["logs"]
    )

    assert (
        "Starting payment-service"
        in combined_logs
    )

    assert (
        "Database connection refused"
        in combined_logs
    )

    print("\nReal Kubernetes logs validated successfully.")

    print("\nCollected logs:")
    for line in data["logs"]:
        print(line)

    print("\nAll assertions passed.")
    print("Real get_pod_logs() tool is working correctly.")


if __name__ == "__main__":
    main()
