from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Literal


ToolPermission = Literal[
    "read_only",
    "write",
    "destructive",
]


@dataclass(frozen=True)
class ToolDefinition:
    """
    Metadata describing a registered AegisAI tool.
    """

    name: str
    description: str
    permission: ToolPermission
    requires_approval: bool
    function: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolExecutionRecord:
    """
    Immutable record describing one tool execution.
    """

    tool_name: str
    arguments: dict[str, Any]
    success: bool
    duration_ms: float
    error: str | None = None


class ToolRegistry:
    """
    Registry for controlled AegisAI tools.

    Every tool must be explicitly registered with metadata
    describing what the tool is allowed to do.

    The registry also records execution metadata for auditing
    and observability.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._execution_history: list[ToolExecutionRecord] = []

    def register(
        self,
        name: str,
        function: Callable[..., dict[str, Any]],
        description: str,
        permission: ToolPermission = "read_only",
        requires_approval: bool = False,
    ) -> None:
        """
        Register a tool with its security metadata.
        """

        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered."
            )

        if permission == "read_only" and requires_approval:
            raise ValueError(
                "Read-only tools cannot require approval."
            )

        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            permission=permission,
            requires_approval=requires_approval,
            function=function,
        )

    def get(
        self,
        name: str,
    ) -> ToolDefinition:
        """
        Retrieve a registered tool definition.
        """

        if name not in self._tools:
            raise KeyError(
                f"Tool '{name}' is not registered."
            )

        return self._tools[name]

    def call(
        self,
        name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute a registered tool and record the execution.

        Tool failures are captured in the audit record and
        then re-raised to the caller.
        """

        tool = self.get(name)

        start_time = perf_counter()

        try:
            result = tool.function(**kwargs)

            duration_ms = (
                perf_counter() - start_time
            ) * 1000

            success = bool(
                result.get("success", False)
            )

            error = None

            if not success:
                error = result.get("error")

            self._execution_history.append(
                ToolExecutionRecord(
                    tool_name=name,
                    arguments=dict(kwargs),
                    success=success,
                    duration_ms=duration_ms,
                    error=error,
                )
            )

            return result

        except Exception as error:
            duration_ms = (
                perf_counter() - start_time
            ) * 1000

            self._execution_history.append(
                ToolExecutionRecord(
                    tool_name=name,
                    arguments=dict(kwargs),
                    success=False,
                    duration_ms=duration_ms,
                    error=str(error),
                )
            )

            raise

    def list_tools(self) -> list[str]:
        """
        Return all registered tool names.
        """

        return sorted(self._tools.keys())

    def describe_tools(self) -> list[dict[str, Any]]:
        """
        Return safe metadata about all registered tools.

        Function objects are intentionally excluded.
        """

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "permission": tool.permission,
                "requires_approval": tool.requires_approval,
            }
            for tool in sorted(
                self._tools.values(),
                key=lambda item: item.name,
            )
        ]

    def get_execution_history(
        self,
    ) -> list[ToolExecutionRecord]:
        """
        Return a copy of the tool execution history.
        """

        return list(self._execution_history)

    def clear_execution_history(self) -> None:
        """
        Clear all recorded tool executions.
        """

        self._execution_history.clear()
