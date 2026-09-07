from backend.app.tools.registry import ToolRegistry


def successful_tool(
    service: str,
) -> dict:
    return {
        "success": True,
        "data": {
            "service": service,
        },
    }


def failing_tool() -> dict:
    return {
        "success": False,
        "error": "Simulated tool failure.",
    }


def crashing_tool() -> dict:
    raise RuntimeError(
        "Simulated unexpected exception."
    )


def main():
    print("=" * 60)
    print("AegisAI - Tool Execution Audit Test")
    print("=" * 60)

    registry = ToolRegistry()

    registry.register(
        name="successful_tool",
        function=successful_tool,
        description="Successful test tool.",
        permission="read_only",
        requires_approval=False,
    )

    registry.register(
        name="failing_tool",
        function=failing_tool,
        description="Failing test tool.",
        permission="read_only",
        requires_approval=False,
    )

    registry.register(
        name="crashing_tool",
        function=crashing_tool,
        description="Crashing test tool.",
        permission="read_only",
        requires_approval=False,
    )

    print("\nRegistered tools:")
    print(registry.list_tools())

    print("\nExecuting successful tool...")

    result = registry.call(
        "successful_tool",
        service="payment-service",
    )

    print(result)

    assert result["success"] is True

    print("\nExecuting failing tool...")

    result = registry.call(
        "failing_tool",
    )

    print(result)

    assert result["success"] is False

    print("\nExecuting crashing tool...")

    try:
        registry.call(
            "crashing_tool",
        )
    except RuntimeError as error:
        print(f"Caught expected exception: {error}")
    else:
        raise AssertionError(
            "Expected RuntimeError was not raised."
        )

    print("\nExecution history:")
    print("-" * 60)

    history = registry.get_execution_history()

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
            f"Duration: {record.duration_ms:.3f} ms"
        )
        print(
            f"Error: {record.error}"
        )
        print("-" * 60)

    assert len(history) == 3

    assert history[0].tool_name == "successful_tool"
    assert history[0].success is True
    assert history[0].error is None

    assert history[1].tool_name == "failing_tool"
    assert history[1].success is False
    assert history[1].error == "Simulated tool failure."

    assert history[2].tool_name == "crashing_tool"
    assert history[2].success is False
    assert (
        history[2].error
        == "Simulated unexpected exception."
    )

    for record in history:
        assert record.duration_ms >= 0

    print("\nTesting history isolation...")

    returned_history = registry.get_execution_history()

    returned_history.clear()

    assert len(
        registry.get_execution_history()
    ) == 3

    print("Execution history is protected from external mutation.")

    print("\nTesting history clearing...")

    registry.clear_execution_history()

    assert (
        registry.get_execution_history()
        == []
    )

    print("Execution history cleared successfully.")

    print("\nAll assertions passed.")
    print("Tool execution audit system is working correctly.")


if __name__ == "__main__":
    main()
