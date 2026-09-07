from backend.app.tools.kubernetes import get_kubernetes_events


def main():
    print("=" * 60)
    print("AegisAI - Real Kubernetes Events Test")
    print("=" * 60)

    print("\nQuerying real Kubernetes events...")

    result = get_kubernetes_events(
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
        data["events"],
        list,
    )

    assert len(data["events"]) > 0

    for event in data["events"]:
        assert event["type"] in [
            "Normal",
            "Warning",
        ]

        assert isinstance(
            event["reason"],
            str,
        )

        assert isinstance(
            event["message"],
            str,
        )

    combined_events = "\n".join(
        event["message"]
        for event in data["events"]
    )

    assert (
        "Back-off restarting failed container"
        in combined_events
        or "BackOff" in combined_events
    )

    print("\nReal Kubernetes events validated successfully.")

    print("\nCollected events:")

    for event in data["events"]:
        print(
            f"[{event['type']}] "
            f"{event['reason']}: "
            f"{event['message']}"
        )

    print("\nAll assertions passed.")
    print(
        "Real get_kubernetes_events() tool "
        "is working correctly."
    )


if __name__ == "__main__":
    main()
