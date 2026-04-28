"""Deterministic recipe runner."""

import json
from pathlib import Path
from typing import Protocol

from pydantic import Field

from ai_crawler.core.models import CrawlResult, FetchResponse, Recipe, RequestSpec
from ai_crawler.core.models.base import DomainModel
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
        with output_path.open("w", encoding="utf-8") as output_file:
            for request in _expand_requests(recipe):
                response = self._fetcher.fetch(request)
                if not _is_success(response):
                    break
                extracted_items = _extract_response_items(response, recipe)
                for item in extracted_items:
                    output_file.write(json.dumps(item, ensure_ascii=False) + "\n")
                    items_written += 1
                if not extracted_items:
                    break

        return CrawlResult(
            recipe_name=recipe.name,
            items_written=items_written,
            output_path=str(output_path),
        )


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
