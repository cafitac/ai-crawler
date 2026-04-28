"""Public SDK facade tests."""

import json

from ai_crawler.core.models import FetchResponse, RequestSpec
from ai_crawler.sdk import AICrawler


class ProductApiFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


def test_sdk_auto_compiles_from_evidence_file_and_returns_report(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
    recipe_path = tmp_path / "recipe.yaml"
    repaired_path = tmp_path / "repaired.recipe.yaml"
    test_output_path = tmp_path / "test.jsonl"
    output_path = tmp_path / "crawl.jsonl"
    report_path = tmp_path / "auto.report.json"
    evidence_path.write_text(
        json.dumps(
            {
                "target_url": "https://example.test/products",
                "goal": "collect products",
                "events": [
                    {
                        "method": "GET",
                        "url": "https://example.test/api/products",
                        "status_code": 200,
                        "resource_type": "fetch",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    crawler = AICrawler(fetcher=ProductApiFetcher())

    result = crawler.auto(
        evidence_path=evidence_path,
        recipe_path=recipe_path,
        repaired_recipe_path=repaired_path,
        initial_output_path=test_output_path,
        final_output_path=output_path,
        report_path=report_path,
        name="products-api",
    )

    assert result.ok is True
    assert result.exit_code == 0
    assert result.report["ok"] is True
    assert result.report["recipe_path"] == str(recipe_path.resolve())
    assert result.report["repaired_recipe_path"] == str(repaired_path.resolve())
    assert result.report["final_crawl_result"]["items_written"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == result.report
    assert output_path.read_text(encoding="utf-8") == '{"name": "Keyboard", "price": 120}\n'


def test_sdk_generate_recipe_writes_yaml(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
    recipe_path = tmp_path / "recipe.yaml"
    evidence_path.write_text(
        json.dumps(
            {
                "target_url": "https://example.test/products",
                "goal": "collect products",
                "events": [
                    {
                        "method": "GET",
                        "url": "https://example.test/api/products",
                        "status_code": 200,
                        "resource_type": "fetch",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = AICrawler(fetcher=ProductApiFetcher()).generate_recipe(
        evidence_path=evidence_path,
        output_path=recipe_path,
        name="products-api",
    )

    assert result.ok is True
    assert result.exit_code == 0
    assert result.report["recipe"]["name"] == "products-api"
    assert recipe_path.exists()
