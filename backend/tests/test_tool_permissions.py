from backend.app.agents.investigation import InvestigationAgent
from backend.app.tools.registry import ToolRegistry


def dummy_tool() -> dict:
    return {
        "success": True,
    }


def main():
    print("=" * 60)
    print("AegisAI - Tool Permission Test")
    print("=" * 60)

    agent = InvestigationAgent()

    print("\nRegistered tools:")
    print(agent.registry.list_tools())

    assert agent.registry.list_tools() == [
        "get_kubernetes_events",
        "get_pod_logs",
        "get_pod_status",
    ]

    print("\nTool metadata:")
    print("-" * 60)

    metadata = agent.registry.describe_tools()

    for tool in metadata:
        print(tool)

        assert tool["permission"] == "read_only"
        assert tool["requires_approval"] is False

    print("\nAll investigation tools are read-only.")

    print("\nTesting invalid permission configuration...")

    registry = ToolRegistry()

    try:
        registry.register(
            name="invalid_tool",
            function=dummy_tool,
            description="Invalid test tool.",
            permission="read_only",
            requires_approval=True,
        )
    except ValueError as error:
        print(f"Blocked correctly: {error}")
    else:
        raise AssertionError(
            "Invalid read-only approval configuration was accepted."
        )

    print("\nTesting unknown tool...")

    try:
        registry.get("delete_database")
    except KeyError as error:
        print(f"Blocked correctly: {error}")
    else:
        raise AssertionError(
            "Unknown tool was not blocked."
        )

    print("\nAll assertions passed.")
    print("Tool permission system is working correctly.")


if __name__ == "__main__":
    main()
