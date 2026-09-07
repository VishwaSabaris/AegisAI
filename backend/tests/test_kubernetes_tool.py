from backend.app.tools.kubernetes import get_pod_status


def main():
    print("=" * 60)
    print("AegisAI - Kubernetes Tool Test")
    print("=" * 60)

    result = get_pod_status("payment-service")

    print("\nTool result:")
    print(result)

    assert result["success"] is True
    assert result["data"]["service"] == "payment-service"
    assert result["data"]["reason"] == "CrashLoopBackOff"
    assert result["data"]["ready"] is False
    assert result["data"]["restart_count"] == 8

    print("\nAll assertions passed.")
    print("Kubernetes read-only tool is working.")


if __name__ == "__main__":
    main()
