import pytest
from pydantic import ValidationError

from ai_crawler.core.models import (
    AgentAction,
    CrawlResult,
    EvidenceBundle,
    ExecutionSpec,
    FailureReport,
    FetchResponse,
    NetworkEvent,
    Recipe,
    RequestSpec,
    ToolResult,
)


def test_fetch_response_round_trips_as_json() -> None:
    response = FetchResponse(
        url="https://example.com/api/products",
        status_code=200,
        headers={"content-type": "application/json"},
        body_text='{"items": []}',
        elapsed_ms=42,
    )

    restored = FetchResponse.model_validate_json(response.model_dump_json())

    assert restored == response


def test_fetch_response_rejects_invalid_status_code() -> None:
    with pytest.raises(ValidationError):
        FetchResponse(
            url="https://example.com/api/products",
            status_code=700,
            headers={},
            body_text="",
            elapsed_ms=1,
        )


def test_evidence_bundle_contains_network_events_without_none_defaults() -> None:
    event = NetworkEvent(
        method="GET",
        url="https://example.com/api/products?page=1",
        status_code=200,
        resource_type="xhr",
    )
    bundle = EvidenceBundle(
        target_url="https://example.com/products",
        goal="collect products",
        events=(event,),
        observations=("JSON API discovered",),
    )

    assert bundle.events == (event,)
    assert bundle.observations == ("JSON API discovered",)
    assert bundle.redactions == ()


def test_agent_action_and_tool_result_round_trip() -> None:
    action = AgentAction(name="inspect_http", arguments={"url": "https://example.com"})
    result = ToolResult(
        action_name=action.name,
        ok=True,
        summary="inspected",
        evidence_refs=("ev-1",),
    )

    restored_action = AgentAction.model_validate_json(action.model_dump_json())
    restored_result = ToolResult.model_validate_json(result.model_dump_json())

    assert restored_action == action
    assert restored_result == result


def test_execution_spec_supports_runner_hardening_fields() -> None:
    execution = ExecutionSpec(
        concurrency=1,
        delay_ms=250,
        max_items=100,
        max_seconds=45,
        retry_attempts=2,
        retry_backoff_ms=500,
        retry_statuses=(500, 502, 503, 504),
        checkpoint_path=".state/products.checkpoint.json",
    )

    assert execution.max_items == 100
    assert execution.max_seconds == 45
    assert execution.retry_attempts == 2
    assert execution.retry_backoff_ms == 500
    assert execution.retry_statuses == (500, 502, 503, 504)
    assert execution.checkpoint_path == ".state/products.checkpoint.json"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_items", -1),
        ("max_seconds", 0),
        ("retry_attempts", -1),
        ("retry_backoff_ms", -1),
    ],
)
def test_execution_spec_rejects_invalid_runner_hardening_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        ExecutionSpec(**{field_name: value})


@pytest.mark.parametrize("retry_statuses", [(199,), (600,), (500, 500)])
def test_execution_spec_rejects_invalid_retry_statuses(retry_statuses: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError):
        ExecutionSpec(retry_statuses=retry_statuses)


def test_recipe_crawl_result_and_failure_report_are_explicit_models() -> None:
    recipe = Recipe(
        name="example-products",
        start_url="https://example.com/products",
        requests=("GET https://example.com/api/products?page=1",),
    )
    crawl_result = CrawlResult(
        recipe_name=recipe.name,
        items_written=2,
        output_path="out.jsonl",
        pages_scheduled=2,
        pages_completed=2,
        pages_failed=0,
        pages_attempted=2,
        requests_attempted=2,
        stop_reason="completed",
        checkpoint_path=".state/example-products.checkpoint.json",
    )
    failure = FailureReport(code="challenge_detected", message="manual handoff required")

    assert recipe.requests == (
        RequestSpec(method="GET", url="https://example.com/api/products?page=1"),
    )
    assert crawl_result.items_written == 2
    assert crawl_result.pages_scheduled == 2
    assert crawl_result.pages_completed == 2
    assert crawl_result.pages_failed == 0
    assert crawl_result.pages_attempted == 2
    assert crawl_result.requests_attempted == 2
    assert crawl_result.stop_reason == "completed"
    assert crawl_result.checkpoint_path == ".state/example-products.checkpoint.json"
    assert failure.retryable is False


@pytest.mark.parametrize("stop_reason", ["", "unknown_stop_reason"])
def test_crawl_result_rejects_unknown_stop_reason(stop_reason: str) -> None:
    with pytest.raises(ValidationError):
        CrawlResult(
            recipe_name="example-products",
            items_written=0,
            output_path="out.jsonl",
            pages_scheduled=0,
            pages_completed=0,
            pages_failed=0,
            pages_attempted=0,
            requests_attempted=0,
            stop_reason=stop_reason,
        )
