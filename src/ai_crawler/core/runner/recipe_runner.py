"""Deterministic recipe runner."""

import json
import time
from pathlib import Path
from typing import Protocol

from pydantic import Field

from ai_crawler.core.models import CrawlResult, FetchResponse, Recipe, RequestSpec
from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.models.recipe import RunnerStopReason
from ai_crawler.core.runner.extraction import extract_items


class RunnerConfig(DomainModel):
    """Configuration for a deterministic recipe run."""

    output_path: str = Field(min_length=1)


class RecipeFetcher(Protocol):
    """Minimal fetcher interface required by RecipeRunner."""

    def fetch(self, request: RequestSpec) -> FetchResponse:
        """Fetch one normalized request."""


class RecipeRunner:
    """Run a validated recipe with a deterministic HTTP fetcher."""

    def __init__(self, fetcher: RecipeFetcher, config: RunnerConfig) -> None:
        self._fetcher = fetcher
        self._config = config

    def run(self, recipe: Recipe) -> CrawlResult:
        """Execute a recipe and write extracted items as JSON Lines."""
        output_path = Path(self._config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        items_written = 0
        pages_attempted = 0
        requests_attempted = 0
        stop_reason: RunnerStopReason = "completed"
        started_at = time.monotonic()
        max_items = recipe.execution.max_items
        max_seconds = recipe.execution.max_seconds
        with output_path.open("w", encoding="utf-8") as output_file:
            for request in _expand_requests(recipe):
                if _max_seconds_reached(started_at, max_seconds, pages_attempted):
                    stop_reason = "max_seconds_reached"
                    break
                pages_attempted += 1
                response, request_attempts, stop_reason = self._fetch_with_retries(
                    request=request,
                    recipe=recipe,
                    started_at=started_at,
                )
                requests_attempted += request_attempts
                if response is None or stop_reason == "non_success_status":
                    break
                extracted_items = _extract_response_items(response, recipe)
                for item in extracted_items:
                    output_file.write(json.dumps(item, ensure_ascii=False) + "\n")
                    items_written += 1
                    if max_items is not None and items_written >= max_items:
                        stop_reason = "max_items_reached"
                        break
                if stop_reason == "max_items_reached":
                    break
                if not extracted_items:
                    stop_reason = "empty_page"
                    break

        return CrawlResult(
            recipe_name=recipe.name,
            items_written=items_written,
            output_path=str(output_path),
            pages_attempted=pages_attempted,
            requests_attempted=requests_attempted,
            stop_reason=stop_reason,
        )

    def _fetch_with_retries(
        self,
        request: RequestSpec,
        recipe: Recipe,
        started_at: float,
    ) -> tuple[FetchResponse | None, int, RunnerStopReason]:
        attempts = 0
        retry_attempts = recipe.execution.retry_attempts
        retry_backoff_ms = recipe.execution.retry_backoff_ms
        retry_statuses = set(recipe.execution.retry_statuses)
        while True:
            attempts += 1
            try:
                response = self._fetcher.fetch(request)
            except Exception:
                if attempts > retry_attempts or _max_seconds_reached_during_retry(
                    started_at,
                    recipe,
                ):
                    return None, attempts, "retry_exhausted"
                _sleep_before_retry(retry_backoff_ms, attempts)
                continue
            if _is_success(response):
                return response, attempts, "completed"
            if response.status_code not in retry_statuses:
                return response, attempts, "non_success_status"
            if attempts > retry_attempts or _max_seconds_reached_during_retry(started_at, recipe):
                return None, attempts, "retry_exhausted"
            _sleep_before_retry(retry_backoff_ms, attempts)


def _expand_requests(recipe: Recipe) -> tuple[RequestSpec, ...]:
    base_request = recipe.requests[0]
    if recipe.pagination.strategy != "query_page":
        return (base_request,)

    query_param = recipe.pagination.query_param
    if not query_param:
        return (base_request,)

    return tuple(
        _request_for_page(base_request, query_param, page)
        for page in range(
            recipe.pagination.start,
            recipe.pagination.start + recipe.pagination.max_pages,
        )
    )


def _request_for_page(request: RequestSpec, query_param: str, page: int) -> RequestSpec:
    query = dict(request.query)
    query[query_param] = str(page)
    return request.model_copy(update={"query": query})


def _is_success(response: FetchResponse) -> bool:
    return 200 <= response.status_code < 300


def _max_seconds_reached(
    started_at: float,
    max_seconds: int | None,
    pages_attempted: int,
) -> bool:
    return (
        max_seconds is not None
        and pages_attempted > 0
        and time.monotonic() - started_at >= max_seconds
    )


def _max_seconds_reached_during_retry(started_at: float, recipe: Recipe) -> bool:
    max_seconds = recipe.execution.max_seconds
    return max_seconds is not None and time.monotonic() - started_at >= max_seconds


def _sleep_before_retry(retry_backoff_ms: int, attempts: int) -> None:
    if retry_backoff_ms <= 0:
        return
    time.sleep((retry_backoff_ms * attempts) / 1000)


def _extract_response_items(
    response: FetchResponse,
    recipe: Recipe,
) -> tuple[dict[str, object], ...]:
    try:
        payload = json.loads(response.body_text)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    return extract_items(
        payload,
        item_path=recipe.extract.item_path,
        fields=recipe.extract.fields,
    )
