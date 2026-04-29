"""Agent tool for deterministic recipe test runs."""
from pydantic import ValidationError

from ai_crawler.core.diagnostics import classify_test_report
from ai_crawler.core.models import (
    AgentAction,
    CrawlResult,
    EvidenceBundle,
    FetchResponse,
    Recipe,
    RequestSpec,
    ToolResult,
)
from ai_crawler.core.runner import RecipeFetcher, RecipeRunner, RunnerConfig
from ai_crawler.core.security import redact_text


class TestRecipeTool:
    """Agent tool that executes a recipe and returns crawl/test report artifacts."""

    def __init__(self, fetcher: RecipeFetcher) -> None:
        self._fetcher = fetcher

    def __call__(self, action: AgentAction, evidence: EvidenceBundle) -> ToolResult:
        recipe = _load_recipe_artifact(action)
        if recipe is None:
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary="missing recipe artifact for test_recipe",
            )
        if isinstance(recipe, InvalidRecipeArtifact):
            return ToolResult(
                action_name=action.name,
                ok=False,
                summary="invalid recipe artifact for test_recipe",
            )

        recording_fetcher = RecordingRecipeFetcher(self._fetcher)
        runner = RecipeRunner(
            fetcher=recording_fetcher,
            config=RunnerConfig(output_path=_output_path(action)),
        )
        crawl_result = runner.run(recipe)
        return ToolResult(
            action_name=action.name,
            ok=True,
            summary=(
                f"tested recipe: {crawl_result.recipe_name} "
                f"items_written={crawl_result.items_written}"
            ),
            artifacts={
                "crawl_result": crawl_result.model_dump(mode="json"),
                "test_report": _test_report(recording_fetcher, crawl_result),
            },
        )


class RecordingRecipeFetcher:
    """Fetcher wrapper that records the first response for repair diagnostics."""

    def __init__(self, fetcher: RecipeFetcher) -> None:
        self._fetcher = fetcher
        self.first_response: FetchResponse | None = None

    def fetch(self, request: RequestSpec) -> FetchResponse:
        response = self._fetcher.fetch(request)
        if self.first_response is None:
            self.first_response = response
        return response


class InvalidRecipeArtifact:
    """Sentinel for malformed recipe artifacts."""


def _load_recipe_artifact(action: AgentAction) -> Recipe | InvalidRecipeArtifact | None:
    artifact = action.arguments.get("recipe")
    if artifact is None:
        return None
    try:
        return Recipe.model_validate(artifact)
    except ValidationError:
        return InvalidRecipeArtifact()


def _test_report(fetcher: RecordingRecipeFetcher, crawl_result: CrawlResult) -> dict[str, object]:
    response = fetcher.first_response
    report: dict[str, object] = {
        "first_response_status": 0,
        "content_type": "",
        "body_sample": "",
        "stop_reason": crawl_result.stop_reason,
        "pages_attempted": crawl_result.pages_attempted,
        "requests_attempted": crawl_result.requests_attempted,
        "failure_reason": _failure_reason(response=response, crawl_result=crawl_result),
    }
    if response is not None:
        report["first_response_status"] = response.status_code
        report["content_type"] = response.headers.get("content-type", "")
        report["body_sample"] = _body_sample(response.body_text)
    report["failure_classification"] = classify_test_report(report)
    return report


def _failure_reason(response: FetchResponse | None, crawl_result: CrawlResult) -> str:
    if crawl_result.stop_reason == "retry_exhausted":
        return "retry_exhausted"
    if response is None:
        return "no_response"
    if not 200 <= response.status_code < 300:
        return "non_success_status"
    if crawl_result.items_written == 0:
        return "no_items_extracted"
    return ""


def _body_sample(body_text: str) -> str:
    return redact_text(body_text[:4000])


def _output_path(action: AgentAction) -> str:
    output_path = action.arguments.get("output_path", "")
    if isinstance(output_path, str) and output_path:
        return output_path
    return "ai-crawler-test.jsonl"
