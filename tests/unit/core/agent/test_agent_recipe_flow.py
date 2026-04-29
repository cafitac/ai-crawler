"""Agent recipe generation and testing flow tests."""

import json
from typing import Any

from ai_crawler.core.agent import (
    AgentController,
    AgentRunConfig,
    AgentToolRegistry,
    GenerateRecipeTool,
    RepairRecipeTool,
)
from ai_crawler.core.agent import (
    TestRecipeTool as RecipeTestTool,
)
from ai_crawler.core.models import (
    AgentAction,
    EvidenceBundle,
    FetchResponse,
    NetworkEvent,
    RequestSpec,
    ToolResult,
)


class HistoryAwareScriptedLLMClient:
    def __init__(self, output_path: str) -> None:
        self._output_path = output_path
        self.seen_histories: list[tuple[ToolResult, ...]] = []

    def next_action(
        self,
        evidence: EvidenceBundle,
        history: tuple[ToolResult, ...],
    ) -> AgentAction:
        self.seen_histories.append(history)
        if not history:
            return AgentAction(
                name="generate_recipe",
                arguments={"name": "products-api"},
            )
        if len(history) == 1:
            return AgentAction(
                name="test_recipe",
                arguments={
                    "recipe": {"$artifact": "recipe"},
                    "output_path": self._output_path,
                },
            )
        return AgentAction(name="stop", arguments={"reason": "recipe tested"})


class RepairAwareScriptedLLMClient:
    def __init__(self, output_path: str) -> None:
        self._output_path = output_path

    def next_action(
        self,
        evidence: EvidenceBundle,
        history: tuple[ToolResult, ...],
    ) -> AgentAction:
        if not history:
            return AgentAction(name="generate_recipe", arguments={"name": "products-api"})
        if len(history) == 1:
            return AgentAction(
                name="test_recipe",
                arguments={
                    "recipe": {"$artifact": "recipe"},
                    "output_path": self._output_path,
                },
            )
        if len(history) == 2:
            return AgentAction(
                name="repair_recipe",
                arguments={
                    "recipe": {"$artifact": "recipe"},
                    "crawl_result": {"$artifact": "crawl_result"},
                    "test_report": {"$artifact": "test_report"},
                },
            )
        if len(history) == 3:
            return AgentAction(
                name="test_recipe",
                arguments={
                    "recipe": {"$artifact": "recipe"},
                    "output_path": self._output_path,
                },
            )
        return AgentAction(name="stop", arguments={"reason": "repaired recipe tested"})


class FakeFetcher:
    def __init__(self) -> None:
        self.requests: list[RequestSpec] = []

    def fetch(self, request: RequestSpec) -> FetchResponse:
        self.requests.append(request)
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


def test_agent_controller_hands_generated_recipe_artifact_to_test_recipe_tool(tmp_path) -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
        events=(
            NetworkEvent(
                method="GET",
                url="https://example.test/api/products",
                status_code=200,
                resource_type="fetch",
            ),
        ),
    )
    output_path = tmp_path / "agent-flow.jsonl"
    llm = HistoryAwareScriptedLLMClient(output_path=str(output_path))
    fetcher = FakeFetcher()
    registry = AgentToolRegistry()
    registry.register("generate_recipe", GenerateRecipeTool())
    registry.register("test_recipe", RecipeTestTool(fetcher=fetcher))
    controller = AgentController(
        llm=llm,
        tools=registry,
        config=AgentRunConfig(max_steps=5),
    )

    result = controller.run(evidence)

    assert result.ok is True
    assert result.stop_reason == "recipe tested"
    assert result.steps_taken == 3
    assert [step.action_name for step in result.history] == ["generate_recipe", "test_recipe"]
    generated_recipe = _artifact(result.history[0], "recipe")
    crawl_result = _artifact(result.history[1], "crawl_result")
    assert generated_recipe["name"] == "products-api"
    assert generated_recipe["requests"][0]["url"] == "https://example.test/api/products"
    assert crawl_result == {
        "recipe_name": "products-api",
        "items_written": 0,
        "output_path": str(output_path),
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "empty_page",
        "checkpoint_path": "",
    }
    assert len(fetcher.requests) == 1
    assert fetcher.requests[0].url == "https://example.test/api/products"
    assert llm.seen_histories[1] == result.history[:1]


def test_agent_controller_repairs_recipe_after_empty_test_result(tmp_path) -> None:
    evidence = EvidenceBundle(
        target_url="https://example.test/products",
        goal="collect products",
        events=(
            NetworkEvent(
                method="GET",
                url="https://example.test/api/products",
                status_code=200,
                resource_type="fetch",
            ),
        ),
    )
    output_path = tmp_path / "agent-repair-flow.jsonl"
    fetcher = FakeFetcher()
    registry = AgentToolRegistry()
    registry.register("generate_recipe", GenerateRecipeTool())
    registry.register("test_recipe", RecipeTestTool(fetcher=fetcher))
    registry.register("repair_recipe", RepairRecipeTool())
    controller = AgentController(
        llm=RepairAwareScriptedLLMClient(output_path=str(output_path)),
        tools=registry,
        config=AgentRunConfig(max_steps=6),
    )

    result = controller.run(evidence)

    assert result.ok is True
    assert result.stop_reason == "repaired recipe tested"
    assert result.steps_taken == 5
    assert [step.action_name for step in result.history] == [
        "generate_recipe",
        "test_recipe",
        "repair_recipe",
        "test_recipe",
    ]
    first_crawl_result = _artifact(result.history[1], "crawl_result")
    repaired_recipe = _artifact(result.history[2], "recipe")
    second_crawl_result = _artifact(result.history[3], "crawl_result")
    assert first_crawl_result["items_written"] == 0
    assert repaired_recipe["extract"] == {
        "item_path": "$.items[*]",
        "fields": {"name": "$.name", "price": "$.price"},
    }
    assert second_crawl_result["items_written"] == 1
    assert output_path.read_text(encoding="utf-8") == '{"name": "Keyboard", "price": 120}\n'
    assert len(fetcher.requests) == 2

def _artifact(result: ToolResult, key: str) -> dict[str, Any]:
    artifact = result.artifacts[key]
    assert isinstance(artifact, dict)
    return artifact
