"""CLI auto command tests."""

import importlib
import json

import yaml

from ai_crawler.core.models import FetchResponse, RequestSpec

cli_main = importlib.import_module("ai_crawler.cli.main")


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


def test_auto_command_uses_defaults_and_writes_final_harness_artifacts(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
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
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "auto",
            str(evidence_path),
            "--recipe",
            str(recipe_path),
            "--repaired-recipe",
            str(repaired_path),
            "--test-output",
            str(test_output_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler auto: recipe=generated-recipe items_written=1 "
        f"output={output_path} report={report_path}"
    )
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
    )
    repaired = yaml.safe_load(repaired_path.read_text(encoding="utf-8"))
    assert repaired["extract"] == {
        "item_path": "$.items[*]",
        "fields": {"name": "$.name", "price": "$.price"},
    }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["recipe_path"] == str(recipe_path)
    assert report["repaired_recipe_path"] == str(repaired_path)
    assert report["progress"] == {
        "items_written": 1,
        "pages_scheduled": 1,
        "pages_completed": 1,
        "pages_failed": 0,
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "completed",
    }
    assert report["final_crawl_result"]["items_written"] == 1
    assert report["initial_failure_classification"]["category"] == "extraction_failed"
    assert report["final_failure_classification"]["category"] == "success"


def test_auto_command_json_mode_prints_machine_readable_report(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    evidence_path = tmp_path / "evidence.json"
    recipe_path = tmp_path / "recipe.yaml"
    repaired_path = tmp_path / "repaired.recipe.yaml"
    output_path = tmp_path / "crawl.jsonl"
    test_output_path = tmp_path / "test.jsonl"
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
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "auto",
            str(evidence_path),
            "--recipe",
            str(recipe_path),
            "--repaired-recipe",
            str(repaired_path),
            "--test-output",
            str(test_output_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--json",
        ]
    )

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["ok"] is True
    assert stdout_report["recipe_path"] == str(recipe_path)
    assert stdout_report["repaired_recipe_path"] == str(repaired_path)
    assert stdout_report["output_path"] == str(output_path)
    assert stdout_report["progress"] == {
        "items_written": 1,
        "pages_scheduled": 1,
        "pages_completed": 1,
        "pages_failed": 0,
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "completed",
    }
    assert stdout_report["final_crawl_result"]["items_written"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report


def test_auto_command_json_mode_returns_failure_exit_code_with_report(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    evidence_path = tmp_path / "evidence.json"
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
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: EmptyApiFetcher())

    exit_code = cli_main.main(
        [
            "auto",
            str(evidence_path),
            "--recipe",
            str(tmp_path / "recipe.yaml"),
            "--repaired-recipe",
            str(tmp_path / "repaired.recipe.yaml"),
            "--test-output",
            str(tmp_path / "test.jsonl"),
            "--output",
            str(tmp_path / "crawl.jsonl"),
            "--report",
            str(report_path),
            "--json",
        ]
    )

    assert exit_code == 2
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["ok"] is False
    assert stdout_report["progress"] == {
        "items_written": 0,
        "pages_scheduled": 1,
        "pages_completed": 1,
        "pages_failed": 0,
        "pages_attempted": 1,
        "requests_attempted": 1,
        "stop_reason": "empty_page",
    }
    assert stdout_report["final_failure_classification"]["category"] == "extraction_failed"
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report


def test_auto_command_accepts_explicit_artifact_paths(tmp_path, monkeypatch, capsys) -> None:
    evidence_path = tmp_path / "evidence.json"
    recipe_path = tmp_path / "artifacts" / "baseline.yaml"
    repaired_path = tmp_path / "artifacts" / "final.yaml"
    output_path = tmp_path / "artifacts" / "items.jsonl"
    test_output_path = tmp_path / "artifacts" / "test.jsonl"
    report_path = tmp_path / "artifacts" / "summary.json"
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
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "auto",
            str(evidence_path),
            "--recipe",
            str(recipe_path),
            "--repaired-recipe",
            str(repaired_path),
            "--test-output",
            str(test_output_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--name",
            "products-api",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        "ai-crawler auto: recipe=products-api items_written=1 "
        f"output={output_path} report={report_path}"
    )
    assert recipe_path.exists()
    assert repaired_path.exists()
    assert output_path.exists()
    assert report_path.exists()
