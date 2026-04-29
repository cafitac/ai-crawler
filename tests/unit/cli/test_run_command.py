"""CLI run command tests."""

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


def test_run_command_loads_recipe_executes_runner_and_prints_summary(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    output_path = tmp_path / "products.jsonl"
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

    exit_code = cli_main.main(["run", str(recipe_path), "--output", str(output_path)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler run: "
        f"recipe=products-api items_written=1 stop_reason=completed output={output_path}"
    )
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
    )
