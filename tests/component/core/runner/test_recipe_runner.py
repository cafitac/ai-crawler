"""Recipe runner component tests."""

import json
import threading
from pathlib import Path

import pytest

import ai_crawler.core.runner.recipe_runner as recipe_runner_module
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


class SequencedFetcher:
    def __init__(self, responses: list[FetchResponse | Exception]) -> None:
        self._responses = responses
        self.calls = 0

    def fetch(self, request: RequestSpec) -> FetchResponse:
        del request
        response = self._responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


class PageAwareFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, request: RequestSpec) -> FetchResponse:
        page = request.query["page"]
        self.urls.append(f"{request.url}?page={page}")
        if page == "2":
            raise TimeoutError("temporary timeout")
        items_by_page = {
            "1": [
                {"id": "p1", "name": "Keyboard", "price": 120},
                {"id": "p2", "name": "Mouse", "price": 40},
            ],
            "3": [],
        }
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": items_by_page[page]}),
            elapsed_ms=5,
        )


class OutOfOrderFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.completed_pages: list[str] = []
        self._lock = threading.Lock()
        self._release_page_one = threading.Event()

    def fetch(self, request: RequestSpec) -> FetchResponse:
        page = request.query["page"]
        with self._lock:
            self.urls.append(f"{request.url}?page={page}")
        if page == "1":
            released = self._release_page_one.wait(timeout=1)
            assert released, "page 1 should be released after later pages complete"
        else:
            with self._lock:
                self.completed_pages.append(page)
                if sorted(self.completed_pages) == ["2", "3"]:
                    self._release_page_one.set()
        items_by_page = {
            "1": [{"id": "p1", "name": "Keyboard", "price": 120}],
            "2": [{"id": "p2", "name": "Mouse", "price": 40}],
            "3": [],
        }
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": items_by_page[page]}),
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


def test_recipe_runner_preserves_request_order_under_concurrency(tmp_path: Path) -> None:
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
            "execution": {"concurrency": 3},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "concurrent-products.jsonl"
    fetcher = OutOfOrderFetcher()
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.items_written == 2
    assert result.pages_attempted == 3
    assert result.requests_attempted == 3
    assert result.stop_reason == "empty_page"
    assert sorted(fetcher.completed_pages) == ["2", "3"]
    written_items = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert written_items == [
        {"name": "Keyboard", "price": 120},
        {"name": "Mouse", "price": 40},
    ]



def test_recipe_runner_rejects_delay_rate_control_with_concurrency(tmp_path: Path) -> None:
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
            "execution": {"concurrency": 2, "delay_ms": 150},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "products.jsonl"
    runner = RecipeRunner(fetcher=FakeFetcher(), config=RunnerConfig(output_path=str(output_path)))

    with pytest.raises(
        ValueError,
        match="execution.delay_ms with concurrency > 1 is not supported yet",
    ):
        runner.run(recipe)



def test_recipe_runner_stops_after_max_items_and_keeps_partial_jsonl_valid(tmp_path: Path) -> None:
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
            "execution": {"max_items": 2},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "guarded-products.jsonl"
    fetcher = FakeFetcher()
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.items_written == 2
    assert result.pages_attempted == 1
    assert result.requests_attempted == 1
    assert result.stop_reason == "max_items_reached"
    assert fetcher.urls == ["https://example.test/api/products?page=1"]
    written_items = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert written_items == [
        {"name": "Keyboard", "price": 120},
        {"name": "Mouse", "price": 40},
    ]


def test_recipe_runner_applies_delay_only_between_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "execution": {"delay_ms": 150},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "delayed-products.jsonl"
    fetcher = FakeFetcher()
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.items_written == 3
    assert result.pages_attempted == 3
    assert result.requests_attempted == 3
    assert result.stop_reason == "empty_page"
    assert sleep_calls == [0.15, 0.15]
    assert fetcher.urls == [
        "https://example.test/api/products?page=1",
        "https://example.test/api/products?page=2",
        "https://example.test/api/products?page=3",
    ]


def test_recipe_runner_skips_delay_after_terminal_stop_condition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "execution": {"delay_ms": 150, "max_items": 2},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "terminal-stop-products.jsonl"
    fetcher = FakeFetcher()
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.items_written == 2
    assert result.pages_attempted == 1
    assert result.requests_attempted == 1
    assert result.stop_reason == "max_items_reached"
    assert sleep_calls == []
    assert fetcher.urls == ["https://example.test/api/products?page=1"]


def test_recipe_runner_stops_before_next_request_when_max_seconds_exceeded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "execution": {"max_seconds": 1},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    output_path = tmp_path / "timed-products.jsonl"
    fetcher = FakeFetcher()
    timeline = iter((0.0, 1.5))
    monkeypatch.setattr(recipe_runner_module.time, "monotonic", lambda: next(timeline))
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert result.items_written == 2
    assert result.pages_attempted == 1
    assert result.requests_attempted == 1
    assert result.stop_reason == "max_seconds_reached"
    assert fetcher.urls == ["https://example.test/api/products?page=1"]
    written_items = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert written_items == [
        {"name": "Keyboard", "price": 120},
        {"name": "Mouse", "price": 40},
    ]


def test_recipe_runner_writes_checkpoint_on_interrupted_run_and_resumes_next_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint_path = tmp_path / "products.checkpoint.json"
    output_path = tmp_path / "products.jsonl"
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
            "execution": {
                "max_seconds": 1,
                "checkpoint_path": str(checkpoint_path),
            },
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    first_fetcher = FakeFetcher()
    first_timeline = iter((0.0, 1.5))
    monkeypatch.setattr(recipe_runner_module.time, "monotonic", lambda: next(first_timeline))
    first_runner = RecipeRunner(
        fetcher=first_fetcher,
        config=RunnerConfig(output_path=str(output_path)),
    )

    first_result = first_runner.run(recipe)

    assert first_result.items_written == 2
    assert first_result.pages_attempted == 1
    assert first_result.requests_attempted == 1
    assert first_result.stop_reason == "max_seconds_reached"
    assert first_result.checkpoint_path == str(checkpoint_path)
    assert first_fetcher.urls == ["https://example.test/api/products?page=1"]
    assert json.loads(checkpoint_path.read_text(encoding="utf-8")) == {
        "recipe_name": "products-api",
        "next_request_index": 1,
        "items_written": 2,
        "output_path": str(output_path),
        "stop_reason": "max_seconds_reached",
    }
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
        '{"name": "Mouse", "price": 40}\n'
    )

    resumed_recipe = recipe.model_copy(
        update={
            "execution": recipe.execution.model_copy(
                update={"max_seconds": None},
            )
        }
    )
    monkeypatch.setattr(recipe_runner_module.time, "monotonic", lambda: 0.0)
    resumed_fetcher = FakeFetcher()
    resumed_runner = RecipeRunner(
        fetcher=resumed_fetcher,
        config=RunnerConfig(output_path=str(output_path)),
    )

    resumed_result = resumed_runner.run(resumed_recipe)

    assert resumed_result.items_written == 3
    assert resumed_result.pages_attempted == 2
    assert resumed_result.requests_attempted == 2
    assert resumed_result.stop_reason == "empty_page"
    assert resumed_result.checkpoint_path == ""
    assert resumed_fetcher.urls == [
        "https://example.test/api/products?page=2",
        "https://example.test/api/products?page=3",
    ]
    assert not checkpoint_path.exists()
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


def test_recipe_runner_retries_retryable_status_once_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = Recipe.model_validate(
        {
            "name": "products-api",
            "start_url": "https://example.test/products",
            "requests": [{"method": "GET", "url": "https://example.test/api/products"}],
            "execution": {
                "retry_attempts": 1,
                "retry_backoff_ms": 250,
                "retry_statuses": [500],
            },
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    fetcher = SequencedFetcher(
        [
            FetchResponse(
                url="https://example.test/api/products",
                status_code=500,
                headers={"content-type": "application/json"},
                body_text='{"items": []}',
                elapsed_ms=5,
            ),
            FetchResponse(
                url="https://example.test/api/products",
                status_code=200,
                headers={"content-type": "application/json"},
                body_text='{"items": [{"name": "Keyboard", "price": 120}]}',
                elapsed_ms=5,
            ),
        ]
    )
    output_path = tmp_path / "retried-products.jsonl"
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert fetcher.calls == 2
    assert sleep_calls == [0.25]
    assert result.items_written == 1
    assert result.pages_attempted == 1
    assert result.requests_attempted == 2
    assert result.stop_reason == "completed"
    assert output_path.read_text(encoding="utf-8") == '{"name": "Keyboard", "price": 120}\n'


def test_recipe_runner_stops_with_retry_exhausted_after_retry_budget_ends(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = Recipe.model_validate(
        {
            "name": "products-api",
            "start_url": "https://example.test/products",
            "requests": [{"method": "GET", "url": "https://example.test/api/products"}],
            "execution": {
                "retry_attempts": 2,
                "retry_backoff_ms": 100,
                "retry_statuses": [500],
            },
        }
    )
    fetcher = SequencedFetcher(
        [
            FetchResponse(
                url="https://example.test/api/products",
                status_code=500,
                headers={"content-type": "application/json"},
                body_text='{"items": []}',
                elapsed_ms=5,
            ),
            FetchResponse(
                url="https://example.test/api/products",
                status_code=500,
                headers={"content-type": "application/json"},
                body_text='{"items": []}',
                elapsed_ms=5,
            ),
            FetchResponse(
                url="https://example.test/api/products",
                status_code=500,
                headers={"content-type": "application/json"},
                body_text='{"items": []}',
                elapsed_ms=5,
            ),
        ]
    )
    output_path = tmp_path / "retry-exhausted.jsonl"
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert fetcher.calls == 3
    assert sleep_calls == [0.1, 0.2]
    assert result.items_written == 0
    assert result.pages_attempted == 1
    assert result.requests_attempted == 3
    assert result.stop_reason == "retry_exhausted"
    assert output_path.read_text(encoding="utf-8") == ""


def test_recipe_runner_keeps_last_checkpoint_when_retry_exhausted_after_progress(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "retry.checkpoint.json"
    output_path = tmp_path / "retry-exhausted-products.jsonl"
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
            "execution": {
                "retry_attempts": 1,
                "checkpoint_path": str(checkpoint_path),
            },
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    runner = RecipeRunner(
        fetcher=PageAwareFetcher(),
        config=RunnerConfig(output_path=str(output_path)),
    )

    result = runner.run(recipe)

    assert result.items_written == 2
    assert result.pages_attempted == 2
    assert result.requests_attempted == 3
    assert result.stop_reason == "retry_exhausted"
    assert result.checkpoint_path == str(checkpoint_path)
    assert json.loads(checkpoint_path.read_text(encoding="utf-8")) == {
        "recipe_name": "products-api",
        "next_request_index": 1,
        "items_written": 2,
        "output_path": str(output_path),
        "stop_reason": "retry_exhausted",
    }
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
        '{"name": "Mouse", "price": 40}\n'
    )


def test_recipe_runner_does_not_retry_non_retryable_challenge_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = Recipe.model_validate(
        {
            "name": "products-api",
            "start_url": "https://example.test/products",
            "requests": [{"method": "GET", "url": "https://example.test/api/products"}],
            "execution": {
                "retry_attempts": 3,
                "retry_backoff_ms": 100,
                "retry_statuses": [500],
            },
        }
    )
    fetcher = SequencedFetcher(
        [
            FetchResponse(
                url="https://example.test/api/products",
                status_code=403,
                headers={"content-type": "text/html"},
                body_text="challenge",
                elapsed_ms=5,
            )
        ]
    )
    output_path = tmp_path / "challenge.jsonl"
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert fetcher.calls == 1
    assert sleep_calls == []
    assert result.requests_attempted == 1
    assert result.stop_reason == "non_success_status"


def test_recipe_runner_retries_transport_error_once_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = Recipe.model_validate(
        {
            "name": "products-api",
            "start_url": "https://example.test/products",
            "requests": [{"method": "GET", "url": "https://example.test/api/products"}],
            "execution": {"retry_attempts": 1, "retry_backoff_ms": 50},
            "extract": {
                "item_path": "$.items[*]",
                "fields": {"name": "$.name", "price": "$.price"},
            },
        }
    )
    fetcher = SequencedFetcher(
        [
            TimeoutError("temporary timeout"),
            FetchResponse(
                url="https://example.test/api/products",
                status_code=200,
                headers={"content-type": "application/json"},
                body_text='{"items": [{"name": "Keyboard", "price": 120}]}',
                elapsed_ms=5,
            ),
        ]
    )
    output_path = tmp_path / "transport-retried-products.jsonl"
    sleep_calls: list[float] = []
    monkeypatch.setattr(recipe_runner_module.time, "sleep", sleep_calls.append)
    runner = RecipeRunner(fetcher=fetcher, config=RunnerConfig(output_path=str(output_path)))

    result = runner.run(recipe)

    assert fetcher.calls == 2
    assert sleep_calls == [0.05]
    assert result.items_written == 1
    assert result.pages_attempted == 1
    assert result.requests_attempted == 2
    assert result.stop_reason == "completed"
