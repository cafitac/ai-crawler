"""Auto recipe compiler tests."""

import json

from ai_crawler.core.agent import AutoRecipeCompiler
from ai_crawler.core.models import EvidenceBundle, FetchResponse, NetworkEvent, RequestSpec


class ProductApiFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


class EmptyApiFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"products": []}),
            elapsed_ms=3,
        )


def test_auto_compiler_generates_tests_repairs_and_retests_recipe(tmp_path) -> None:
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
    final_output = tmp_path / "crawl.jsonl"
    initial_output = tmp_path / "test.jsonl"

    result = AutoRecipeCompiler(fetcher=ProductApiFetcher()).compile(
        evidence=evidence,
        recipe_name="products-api",
        initial_output_path=str(initial_output),
        final_output_path=str(final_output),
    )

    assert result.ok is True
    assert result.recipe.name == "products-api"
    assert result.initial_crawl_result.items_written == 0
    assert result.final_crawl_result.items_written == 1
    assert result.initial_failure_classification["category"] == "extraction_failed"
    assert result.final_failure_classification["category"] == "success"
    assert result.repaired_recipe.extract.item_path == "$.items[*]"
    assert result.repaired_recipe.extract.fields == {"name": "$.name", "price": "$.price"}
    assert final_output.read_text(encoding="utf-8") == '{"name": "Keyboard", "price": 120}\n'


def test_auto_compiler_marks_failed_when_repair_writes_no_items(tmp_path) -> None:
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

    result = AutoRecipeCompiler(fetcher=EmptyApiFetcher()).compile(
        evidence=evidence,
        recipe_name="products-api",
        initial_output_path=str(tmp_path / "test.jsonl"),
        final_output_path=str(tmp_path / "crawl.jsonl"),
    )

    assert result.ok is False
    assert result.final_crawl_result.items_written == 0
    assert result.final_failure_classification["category"] == "extraction_failed"
