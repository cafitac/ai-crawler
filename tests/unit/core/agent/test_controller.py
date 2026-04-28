"""AgentController loop tests."""

from ai_crawler.core.agent import AgentController, AgentRunConfig, AgentToolRegistry
from ai_crawler.core.models import AgentAction, EvidenceBundle, ToolResult


class ScriptedLLMClient:
    def __init__(self, actions: tuple[AgentAction, ...]) -> None:
        self._actions = list(actions)
        self.seen_steps: list[tuple[str, tuple[ToolResult, ...]]] = []

    def next_action(
        self,
        evidence: EvidenceBundle,
        history: tuple[ToolResult, ...],
    ) -> AgentAction:
        self.seen_steps.append((evidence.target_url, history))
        return self._actions.pop(0)


def test_agent_controller_executes_actions_until_stop() -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
    )
    llm = ScriptedLLMClient(
        actions=(
            AgentAction(name="inspect_http", arguments={"url": evidence.target_url}),
            AgentAction(name="stop", arguments={"reason": "recipe ready"}),
        )
    )
    registry = AgentToolRegistry()
    registry.register(
        "inspect_http",
        lambda action, current_evidence: ToolResult(
            action_name=action.name,
            ok=True,
            summary=f"inspected {current_evidence.target_url}",
            evidence_refs=("http-1",),
        ),
    )
    controller = AgentController(
        llm=llm,
        tools=registry,
        config=AgentRunConfig(max_steps=5),
    )

    result = controller.run(evidence)

    assert result.ok is True
    assert result.stop_reason == "recipe ready"
    assert result.steps_taken == 2
    assert result.history == (
        ToolResult(
            action_name="inspect_http",
            ok=True,
            summary="inspected https://example.test/products",
            evidence_refs=("http-1",),
        ),
    )
    assert len(llm.seen_steps) == 2
    assert llm.seen_steps[1][1] == result.history


def test_agent_controller_records_unknown_action_failure_and_continues() -> None:
    evidence = EvidenceBundle(target_url="https://example.test", goal="collect")
    llm = ScriptedLLMClient(
        actions=(
            AgentAction(name="missing_tool", arguments={}),
            AgentAction(name="stop", arguments={}),
        )
    )
    controller = AgentController(
        llm=llm,
        tools=AgentToolRegistry(),
        config=AgentRunConfig(max_steps=3),
    )

    result = controller.run(evidence)

    assert result.ok is True
    assert result.stop_reason == "stop action received"
    assert result.history == (
        ToolResult(
            action_name="missing_tool",
            ok=False,
            summary="unknown action: missing_tool",
        ),
    )


def test_agent_controller_stops_when_max_steps_is_reached() -> None:
    evidence = EvidenceBundle(target_url="https://example.test", goal="collect")
    llm = ScriptedLLMClient(
        actions=(
            AgentAction(name="missing_tool", arguments={}),
            AgentAction(name="missing_tool", arguments={}),
        )
    )
    controller = AgentController(
        llm=llm,
        tools=AgentToolRegistry(),
        config=AgentRunConfig(max_steps=2),
    )

    result = controller.run(evidence)

    assert result.ok is False
    assert result.stop_reason == "max steps reached"
    assert result.steps_taken == 2
    assert len(result.history) == 2
