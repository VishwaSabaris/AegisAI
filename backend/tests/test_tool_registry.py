from backend.app.tools.kubernetes import get_pod_status
from backend.app.tools.registry import ToolRegistry


def main():
    print("=" * 60)
    print("AegisAI - Tool Registry Test")
    print("=" * 60)

    registry = ToolRegistry()

    registry.register(
        "get_pod_status",
        get_pod_status,
    )

    print("\nRegistered tools:")
    print(registry.list_tools())

    assert registry.list_tools() == ["get_pod_status"]

    print("\nCalling get_pod_status through registry...")

    result = registry.call(
        "get_pod_status",
        service="payment-service",
    )

    print("\nTool result:")
    print(result)

    assert result["success"] is True
    assert result["data"]["service"] == "payment-service"
    assert result["data"]["reason"] == "CrashLoopBackOff"

    print("\nTesting unknown tool...")

    try:
        registry.call(
            "delete_database",
        )
    except KeyError as error:
        print(f"Blocked correctly: {error}")
    else:
        raise AssertionError(
            "Unknown tool was not blocked."
        )

    print("\nAll assertions passed.")
    print("Tool Registry is working correctly.")


if __name__ == "__main__":
    main()
