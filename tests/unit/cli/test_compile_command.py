"""CLI compile one-command tests."""

import importlib
import json

from ai_crawler.core.models import EvidenceBundle, FetchResponse, NetworkEvent, RequestSpec

cli_main = importlib.import_module("ai_crawler.cli.main")


class FakeProbe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def probe(self, url: str, goal: str) -> EvidenceBundle:
        self.calls.append((url, goal))
        return EvidenceBundle(
            target_url=url,
            goal=goal,
            events=(
                NetworkEvent(
                    method="GET",
                    url="https://example.test/api/products",
                    status_code=200,
                    resource_type="fetch",
                ),
            ),
            observations=("captured 1 browser network event(s)",),
        )


class ProductApiFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


def test_compile_command_probes_then_auto_compiles_with_defaults(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    fake_probe = FakeProbe()
    evidence_path = tmp_path / "evidence.json"
    recipe_path = tmp_path / "recipe.yaml"
    repaired_path = tmp_path / "repaired.recipe.yaml"
    test_output_path = tmp_path / "test.jsonl"
    output_path = tmp_path / "crawl.jsonl"
    report_path = tmp_path / "auto.report.json"
    monkeypatch.setattr(cli_main, "create_default_probe", lambda: fake_probe)
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "compile",
            "https://example.test/products",
            "--goal",
            "collect products",
            "--evidence",
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
    assert fake_probe.calls == [("https://example.test/products", "collect products")]
    assert capsys.readouterr().out.strip() == (
        "ai-crawler compile: recipe=generated-recipe items_written=1 "
        f"evidence={evidence_path} output={output_path} report={report_path}"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["target_url"] == "https://example.test/products"
    assert evidence["goal"] == "collect products"
    assert evidence["events"][0]["url"] == "https://example.test/api/products"
    assert output_path.read_text(encoding="utf-8") == (
        '{"name": "Keyboard", "price": 120}\n'
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["evidence_path"] == str(evidence_path)
    assert report["final_crawl_result"]["items_written"] == 1


def test_compile_command_json_mode_prints_only_machine_readable_report(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    fake_probe = FakeProbe()
    evidence_path = tmp_path / "evidence.json"
    report_path = tmp_path / "auto.report.json"
    monkeypatch.setattr(cli_main, "create_default_probe", lambda: fake_probe)
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "compile",
            "https://example.test/products",
            "--evidence",
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

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["ok"] is True
    assert stdout_report["evidence_path"] == str(evidence_path)
    assert stdout_report["final_crawl_result"]["items_written"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report
