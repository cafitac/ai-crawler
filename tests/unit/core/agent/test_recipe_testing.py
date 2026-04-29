"""Recipe testing tool tests."""

import json

from ai_crawler.core.agent import TestRecipeTool as RecipeTestTool
from ai_crawler.core.models import AgentAction, EvidenceBundle, FetchResponse, Recipe, RequestSpec


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
            elapsed_ms=4,
        )


class ChallengeFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=403,
            headers={"content-type": "text/html"},
            body_text="<html><title>Just a moment...</title>Checking your browser</html>",
            elapsed_ms=3,
        )


class RetryExhaustedFetcher:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, request: RequestSpec) -> FetchResponse:
        self.calls += 1
        return FetchResponse(
            url=request.url,
            status_code=500,
            headers={"content-type": "application/json"},
            body_text='{"error": "temporary"}',
            elapsed_ms=3,
        )


def test_test_recipe_tool_runs_recipe_and_returns_crawl_result_artifact(tmp_path) -> None:
    recipe = Recipe(
        name="products-api",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
        extract={"item_path": "$.items[*]", "fields": {"name": "$.name", "price": "$.price"}},
    )
    output_path = tmp_path / "probe.jsonl"
    fetcher = FakeFetcher()
    tool = RecipeTestTool(fetcher=fetcher)
    action = AgentAction(
        name="test_recipe",
        arguments={
            "recipe": recipe.model_dump(mode="json"),
            "output_path": str(output_path),
        },
    )

    result = tool(action, EvidenceBundle(target_url=recipe.start_url, goal="collect products"))

    assert result.ok is True
    assert result.action_name == "test_recipe"
    assert result.summary == "tested recipe: products-api items_written=1"
    assert result.artifacts["crawl_result"] == {
        "recipe_name": "products-api",
        "items_written": 1,
        "output_path": str(output_path),
        "pages_scheduled": 1,
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "completed",
        "checkpoint_path": "",
    }
    assert result.artifacts["test_report"] == {
        "first_response_status": 200,
        "content_type": "application/json",
        "body_sample": '{"items": [{"name": "Keyboard", "price": 120}]}',
        "stop_reason": "completed",
        "pages_scheduled": 1,
        "pages_attempted": 1,
        "requests_attempted": 1,
        "failure_reason": "",
        "failure_classification": {
            "category": "success",
            "retryable": False,
            "requires_human": False,
            "summary": "test request completed successfully",
        },
    }
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
    )
    assert tuple(fetcher.requests) == recipe.requests


def test_test_recipe_tool_classifies_challenge_boundary(tmp_path) -> None:
    recipe = Recipe(
        name="challenge-page",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
    )
    tool = RecipeTestTool(fetcher=ChallengeFetcher())
    action = AgentAction(
        name="test_recipe",
        arguments={
            "recipe": recipe.model_dump(mode="json"),
            "output_path": str(tmp_path / "challenge.jsonl"),
        },
    )

    result = tool(action, EvidenceBundle(target_url=recipe.start_url, goal="collect products"))

    test_report = result.artifacts["test_report"]
    assert test_report["stop_reason"] == "non_success_status"
    assert test_report["pages_scheduled"] == 1
    assert test_report["pages_attempted"] == 1
    assert test_report["requests_attempted"] == 1
    assert test_report["failure_reason"] == "non_success_status"
    assert test_report["failure_classification"] == {
        "category": "challenge_detected",
        "retryable": False,
        "requires_human": True,
        "summary": "challenge boundary detected; manual handoff or authorized session is required",
    }


def test_test_recipe_tool_reports_retry_exhaustion_as_retryable_failure(tmp_path) -> None:
    recipe = Recipe(
        name="flaky-api",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
        execution={"retry_attempts": 2, "retry_backoff_ms": 10, "retry_statuses": (500,)},
    )
    fetcher = RetryExhaustedFetcher()
    tool = RecipeTestTool(fetcher=fetcher)
    action = AgentAction(
        name="test_recipe",
        arguments={
            "recipe": recipe.model_dump(mode="json"),
            "output_path": str(tmp_path / "retry-exhausted.jsonl"),
        },
    )

    result = tool(action, EvidenceBundle(target_url=recipe.start_url, goal="collect products"))

    test_report = result.artifacts["test_report"]
    assert fetcher.calls == 3
    assert test_report["stop_reason"] == "retry_exhausted"
    assert test_report["pages_scheduled"] == 1
    assert test_report["pages_attempted"] == 1
    assert test_report["requests_attempted"] == 3
    assert test_report["failure_reason"] == "retry_exhausted"
    assert test_report["failure_classification"] == {
        "category": "retry_exhausted",
        "retryable": True,
        "requires_human": False,
        "summary": "retry budget exhausted after transient request failures",
    }


def test_test_recipe_tool_returns_failure_without_recipe_artifact(tmp_path) -> None:
    tool = RecipeTestTool(fetcher=FakeFetcher())
    action = AgentAction(
        name="test_recipe",
        arguments={"output_path": str(tmp_path / "out.jsonl")},
    )

    result = tool(action, EvidenceBundle(target_url="https://example.test", goal="collect"))

    assert result.ok is False
    assert result.action_name == "test_recipe"
    assert result.summary == "missing recipe artifact for test_recipe"
    assert result.artifacts == {}


def test_test_recipe_tool_returns_failure_for_invalid_recipe_artifact(tmp_path) -> None:
    tool = RecipeTestTool(fetcher=FakeFetcher())
    action = AgentAction(
        name="test_recipe",
        arguments={
            "recipe": {"name": "bad"},
            "output_path": str(tmp_path / "out.jsonl"),
        },
    )

    result = tool(action, EvidenceBundle(target_url="https://example.test", goal="collect"))

    assert result.ok is False
    assert result.action_name == "test_recipe"
    assert result.summary == "invalid recipe artifact for test_recipe"
    assert result.artifacts == {}
