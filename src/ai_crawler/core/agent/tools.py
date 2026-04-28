"""Tool registry for deterministic agent action execution."""

from collections.abc import Callable

from ai_crawler.core.models import AgentAction, EvidenceBundle, ToolResult

AgentTool = Callable[[AgentAction, EvidenceBundle], ToolResult]


class AgentToolRegistry:
    """Registry of deterministic tools callable by AgentController."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, name: str, tool: AgentTool) -> None:
        """Register a tool for one action name."""
        self._tools[name] = tool

    def execute(self, action: AgentAction, evidence: EvidenceBundle) -> ToolResult:
        """Execute a registered tool or return an explicit failure result."""
        tool = self._tools.get(action.name)
        if tool is None:
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary=f"unknown action: {action.name}",
            )
        return tool(action, evidence)
