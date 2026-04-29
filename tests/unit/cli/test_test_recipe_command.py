"""CLI test-recipe command tests."""

import importlib
import json

from ai_crawler.core.models import FetchResponse, RequestSpec

cli_main = importlib.import_module("ai_crawler.cli.main")


class FakeFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


def test_test_recipe_command_executes_tool_writes_report_and_prints_summary(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    output_path = tmp_path / "products.jsonl"
    report_path = tmp_path / "report.json"
    recipe_path.write_text(
        """
name: products-api
start_url: https://example.test/products
requests:
  - method: GET
    url: https://example.test/api/products
extract:
  item_path: $.items[*]
  fields:
    name: $.name
    price: $.price
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: FakeFetcher())

    exit_code = cli_main.main(
        [
            "test-recipe",
            str(recipe_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler test-recipe: "
        f"recipe=products-api items_written=1 failure_reason= output={output_path} "
        f"report={report_path}"
    )
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["crawl_result"] == {
        "recipe_name": "products-api",
        "items_written": 1,
        "output_path": str(output_path),
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "completed",
        "checkpoint_path": "",
    }
    assert report["test_report"] == {
        "first_response_status": 200,
        "content_type": "application/json",
        "body_sample": '{"items": [{"name": "Keyboard", "price": 120}]}',
        "failure_reason": "",
        "failure_classification": {
            "category": "success",
            "retryable": False,
            "requires_human": False,
            "summary": "test request completed successfully",
        },
    }
