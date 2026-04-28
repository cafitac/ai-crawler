"""CLI repair-recipe command tests."""

import importlib
import json

cli_main = importlib.import_module("ai_crawler.cli.main")


def test_repair_recipe_command_uses_simple_defaults_and_writes_repaired_recipe(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "repaired.recipe.yaml"
    recipe_path.write_text(
        """
name: products-api
start_url: https://example.test/products
requests:
  - method: GET
    url: https://example.test/api/products
""".strip(),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "crawl_result": {
                    "recipe_name": "products-api",
                    "items_written": 0,
                    "output_path": str(tmp_path / "products.jsonl"),
                },
                "test_report": {
                    "first_response_status": 200,
                    "content_type": "application/json",
                    "body_sample": json.dumps(
                        {"items": [{"name": "Keyboard", "price": 120, "tags": ["sale"]}]}
                    ),
                    "failure_reason": "no_items_extracted",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = cli_main.main(["repair-recipe", str(recipe_path)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler repair-recipe: recipe=products-api "
        f"output={output_path} report={report_path}"
    )
    repaired = output_path.read_text(encoding="utf-8")
    assert "item_path: $.items[*]" in repaired
    assert "name: $.name" in repaired
    assert "price: $.price" in repaired
    assert "tags" not in repaired


def test_repair_recipe_command_accepts_explicit_report_and_output(tmp_path, capsys) -> None:
    recipe_path = tmp_path / "input.yaml"
    report_path = tmp_path / "diagnostics.json"
    output_path = tmp_path / "custom.yaml"
    recipe_path.write_text(
        """
name: already-good
start_url: https://example.test/products
requests:
  - method: GET
    url: https://example.test/api/products
extract:
  item_path: $.items[*]
  fields:
    name: $.name
""".strip(),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "crawl_result": {
                    "recipe_name": "already-good",
                    "items_written": 1,
                    "output_path": str(tmp_path / "items.jsonl"),
                },
                "test_report": {"failure_reason": ""},
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main.main(
        [
            "repair-recipe",
            str(recipe_path),
            "--report",
            str(report_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler repair-recipe: recipe=already-good "
        f"output={output_path} report={report_path}"
    )
    repaired = output_path.read_text(encoding="utf-8")
    assert "name: already-good" in repaired
    assert "item_path: $.items[*]" in repaired
