"""Recipe runner component tests."""

import json
from pathlib import Path

from ai_crawler.core.models import FetchResponse, Recipe, RequestSpec
from ai_crawler.core.runner import RecipeRunner, RunnerConfig


class FakeFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, request: RequestSpec) -> FetchResponse:
        self.urls.append(f"{request.url}?page={request.query['page']}")
        items_by_page = {
            "1": [
                {"id": "p1", "name": "Keyboard", "price": 120},
                {"id": "p2", "name": "Mouse", "price": 40},
            ],
            "2": [{"id": "p3", "name": "Monitor", "price": 300}],
            "3": [],
        }
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": items_by_page[request.query["page"]]}),
            elapsed_ms=5,
        )


def test_recipe_runner_executes_query_page_pagination_to_jsonl(tmp_path: Path) -> None:
    recipe = Recipe.model_validate(
        {
            "name": "products-api",
            "start_url": "https://example.test/products",
            "requests": [
                {
                    "id": "list-products",
                    "method": "GET",
                    "url": "https://example.test/api/products",
                    "query": {"page": "1"},
                }
            ],
            "pagination": {
                "strategy": "query_page",
                "query_param": "page",
                "start": 1,
                "max_pages": 3,
            },
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "products.jsonl"
    fetcher = FakeFetcher()
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.recipe_name == "products-api"
    assert result.items_written == 3
    assert result.output_path == str(output_path)
    assert result.pages_attempted == 3
    assert result.requests_attempted == 3
    assert result.stop_reason == "empty_page"
    assert result.checkpoint_path == ""
    assert fetcher.urls == [
        "https://example.test/api/products?page=1",
        "https://example.test/api/products?page=2",
        "https://example.test/api/products?page=3",
    ]
    written_items = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert written_items == [
        {"name": "Keyboard", "price": 120},
        {"name": "Mouse", "price": 40},
        {"name": "Monitor", "price": 300},
    ]


def test_recipe_runner_stops_on_non_success_response(tmp_path: Path) -> None:
    class FailingFetcher:
        def fetch(self, request: RequestSpec) -> FetchResponse:
            return FetchResponse(
                url=request.url,
                status_code=403,
                headers={"content-type": "text/html"},
                body_text="challenge",
                elapsed_ms=1,
            )

    recipe = Recipe(
        name="blocked",
        start_url="https://example.test/products",
        requests=(RequestSpec(method="GET", url="https://example.test/api/products"),),
    )
    output_path = tmp_path / "blocked.jsonl"
    runner = RecipeRunner(
        fetcher=FailingFetcher(),
        config=RunnerConfig(output_path=str(output_path)),
    )

    result = runner.run(recipe)

    assert result.items_written == 0
    assert result.pages_attempted == 1
    assert result.requests_attempted == 1
    assert result.stop_reason == "non_success_status"
    assert output_path.read_text(encoding="utf-8") == ""
