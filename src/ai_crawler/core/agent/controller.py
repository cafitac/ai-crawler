"""AgentController structured action loop."""

from typing import Any

from pydantic import Field

from ai_crawler.core.agent.llm import LLMClient
from ai_crawler.core.agent.tools import AgentToolRegistry
from ai_crawler.core.models import AgentAction, AgentRunResult, EvidenceBundle, ToolResult
from ai_crawler.core.models.base import DomainModel


class AgentRunConfig(DomainModel):
    """Limits for one AI-controlled action loop."""

    max_steps: int = Field(default=8, ge=1)


DEFAULT_AGENT_RUN_CONFIG = AgentRunConfig()


class AgentController:
    """Control-plane loop where an LLM selects actions and tools execute them."""

    def __init__(
        self,
        llm: LLMClient,
        tools: AgentToolRegistry,
        config: AgentRunConfig = DEFAULT_AGENT_RUN_CONFIG,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._config = config

    def run(self, evidence: EvidenceBundle) -> AgentRunResult:
        """Run the action loop until stop or max_steps."""
        history: tuple[ToolResult, ...] = ()

        for step_index in range(self._config.max_steps):
            action = self._llm.next_action(evidence=evidence, history=history)
            action = resolve_action_artifacts(action=action, history=history)
            steps_taken = step_index + 1

            if action.name == "stop":
                return AgentRunResult(
                    ok=True,
                    stop_reason=_stop_reason(action.arguments),
                    steps_taken=steps_taken,
                    history=history,
                )

            tool_result = self._tools.execute(action=action, evidence=evidence)
            history = (*history, tool_result)

        return AgentRunResult(
            ok=False,
            stop_reason="max steps reached",
            steps_taken=self._config.max_steps,
            history=history,
        )


def resolve_action_artifacts(action: AgentAction, history: tuple[ToolResult, ...]) -> AgentAction:
    """Resolve lightweight artifact references in action arguments."""
    resolved_arguments = _resolve_value(action.arguments, history)
    if not isinstance(resolved_arguments, dict):
        return action
    return action.model_copy(update={"arguments": resolved_arguments})


def _resolve_value(value: Any, history: tuple[ToolResult, ...]) -> Any:
    if _is_artifact_ref(value):
        artifact_name = value["$artifact"]
        return _latest_artifact(history=history, artifact_name=artifact_name)
    if isinstance(value, dict):
        return {key: _resolve_value(item, history) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, history) for item in value]
    return value


def _is_artifact_ref(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value.keys()) == {"$artifact"}
        and isinstance(value["$artifact"], str)
        and bool(value["$artifact"])
    )


def _latest_artifact(history: tuple[ToolResult, ...], artifact_name: str) -> Any:
    for result in reversed(history):
        if artifact_name in result.artifacts:
            return result.artifacts[artifact_name]
    return {"$artifact": artifact_name}


def _stop_reason(arguments: dict[str, object]) -> str:
    reason = arguments.get("reason", "")
    if isinstance(reason, str) and reason:
        return reason
    return "stop action received"
