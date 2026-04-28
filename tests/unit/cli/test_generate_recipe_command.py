"""CLI generate-recipe command tests."""

import importlib
import json

import yaml

cli_main = importlib.import_module("ai_crawler.cli.main")


def test_generate_recipe_command_loads_evidence_writes_yaml_and_prints_summary(
    tmp_path,
    capsys,
) -> None:
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
                        "url": "https://example.test/static/app.js",
                        "status_code": 200,
                        "resource_type": "script",
                    },
                    {
                        "method": "GET",
                        "url": "https://example.test/api/products",
                        "status_code": 200,
                        "resource_type": "fetch",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main.main(
        ["generate-recipe", str(evidence_path), "--output", str(recipe_path)]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        f"ai-crawler generate-recipe: recipe=generated-recipe output={recipe_path}"
    )
    recipe_payload = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    assert recipe_payload["name"] == "generated-recipe"
    assert recipe_payload["start_url"] == "https://example.test/products"
    assert recipe_payload["requests"] == [
        {
            "id": "",
            "method": "GET",
            "url": "https://example.test/api/products",
            "headers": {},
            "query": {},
            "cookies": {},
            "body": "",
        }
    ]


def test_generate_recipe_command_accepts_custom_recipe_name(tmp_path, capsys) -> None:
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

    exit_code = cli_main.main(
        [
            "generate-recipe",
            str(evidence_path),
            "--output",
            str(recipe_path),
            "--name",
            "products-api",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        f"ai-crawler generate-recipe: recipe=products-api output={recipe_path}"
    )
    assert yaml.safe_load(recipe_path.read_text(encoding="utf-8"))["name"] == "products-api"
