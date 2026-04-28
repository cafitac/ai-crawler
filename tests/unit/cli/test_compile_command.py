"""CLI compile one-command tests."""

import importlib
import json

import pytest

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


class EmptyProbe:
    def probe(self, url: str, goal: str) -> EvidenceBundle:
        return EvidenceBundle(
            target_url=url,
            goal=goal,
            events=(),
            observations=("captured 0 browser network event(s)",),
        )


class SensitiveFailingProbe:
    def probe(self, url: str, goal: str) -> EvidenceBundle:
        raise RuntimeError("navigation failed token=abcdef123456")


class ProbeFactory:
    def __init__(self, probe) -> None:
        self.probe = probe
        self.configs = []

    def __call__(self, config=None):
        self.configs.append(config)
        return self.probe


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
    monkeypatch.setattr(cli_main, "create_default_probe", lambda config=None: fake_probe)
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
    assert report["command_type"] == "compile"
    assert report["failure_phase"] == ""
    assert [phase["name"] for phase in report["phase_diagnostics"]] == [
        "probe",
        "generate",
        "initial_test",
        "repair",
        "final_test",
    ]
    assert all(phase["status"] == "success" for phase in report["phase_diagnostics"])
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
    monkeypatch.setattr(cli_main, "create_default_probe", lambda config=None: fake_probe)
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
    assert stdout_report["command_type"] == "compile"
    assert stdout_report["failure_phase"] == ""
    assert stdout_report["evidence_path"] == str(evidence_path)
    assert stdout_report["final_crawl_result"]["items_written"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report


def test_compile_command_json_mode_reports_no_endpoint_candidates(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    evidence_path = tmp_path / "evidence.json"
    report_path = tmp_path / "auto.report.json"
    monkeypatch.setattr(cli_main, "create_default_probe", lambda config=None: EmptyProbe())
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

    captured = capsys.readouterr()
    stdout_report = json.loads(captured.out)
    assert exit_code == 2
    assert stdout_report["ok"] is False
    assert stdout_report["command_type"] == "compile"
    assert stdout_report["failure_phase"] == "generate"
    assert stdout_report["failure_classification"] == {
        "category": "no_endpoint_candidates",
        "retryable": True,
        "requires_human": False,
    }
    assert stdout_report["evidence_path"] == str(evidence_path)
    expected_summary = (
        "no useful network endpoint candidates were captured; inspect evidence or retry "
        "probe with an authorized target"
    )
    assert stdout_report["phase_diagnostics"] == [
        {
            "name": "probe",
            "status": "success",
            "summary": "captured 0 network event(s)",
        },
        {
            "name": "generate",
            "status": "failed",
            "summary": expected_summary,
        },
    ]
    assert "no useful network endpoint candidates" in captured.err
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report


def test_compile_command_json_mode_reports_final_test_failure_phase(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    evidence_path = tmp_path / "evidence.json"
    report_path = tmp_path / "auto.report.json"
    monkeypatch.setattr(cli_main, "create_default_probe", lambda config=None: FakeProbe())
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: EmptyApiFetcher())

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

    stdout_report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert stdout_report["ok"] is False
    assert stdout_report["failure_phase"] == "final_test"
    assert stdout_report["phase_diagnostics"][-1]["name"] == "final_test"
    assert stdout_report["phase_diagnostics"][-1]["status"] == "failed"
    assert stdout_report["final_failure_classification"]["category"] == "extraction_failed"
    assert json.loads(report_path.read_text(encoding="utf-8")) == stdout_report


def test_compile_command_json_mode_redacts_probe_failure_summary(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    report_path = tmp_path / "auto.report.json"
    monkeypatch.setattr(
        cli_main,
        "create_default_probe",
        lambda config=None: SensitiveFailingProbe(),
    )

    exit_code = cli_main.main(
        [
            "compile",
            "https://example.test/products",
            "--evidence",
            str(tmp_path / "evidence.json"),
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

    captured = capsys.readouterr()
    stdout_report = json.loads(captured.out)
    report_text = report_path.read_text(encoding="utf-8")
    assert exit_code == 2
    assert stdout_report["failure_phase"] == "probe"
    assert stdout_report["failure_classification"]["category"] == "probe_failed"
    assert "abcdef123456" not in captured.err
    assert "abcdef123456" not in captured.out
    assert "abcdef123456" not in report_text
    assert "token=[REDACTED]" in captured.err
    assert json.loads(report_text) == stdout_report


def test_compile_command_accepts_probe_tuning_options(tmp_path, monkeypatch) -> None:
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)
    monkeypatch.setattr(cli_main, "create_default_fetcher", lambda: ProductApiFetcher())

    exit_code = cli_main.main(
        [
            "compile",
            "https://example.test/products",
            "--wait-ms",
            "2500",
            "--max-events",
            "9",
            "--include-resource-type",
            "document,xhr",
            "--evidence",
            str(tmp_path / "evidence.json"),
            "--recipe",
            str(tmp_path / "recipe.yaml"),
            "--repaired-recipe",
            str(tmp_path / "repaired.recipe.yaml"),
            "--test-output",
            str(tmp_path / "test.jsonl"),
            "--output",
            str(tmp_path / "crawl.jsonl"),
            "--report",
            str(tmp_path / "auto.report.json"),
        ]
    )

    assert exit_code == 0
    config = probe_factory.configs[0]
    assert config.wait_after_load_ms == 2500
    assert config.max_events == 9
    assert config.include_resource_types == ("document", "xhr")


def test_compile_command_rejects_invalid_probe_tuning_before_probe(tmp_path, monkeypatch) -> None:
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)

    with pytest.raises(SystemExit) as error:
        cli_main.main(
            [
                "compile",
                "https://example.test/products",
                "--max-events",
                "0",
                "--evidence",
                str(tmp_path / "evidence.json"),
                "--json",
            ]
        )

    assert error.value.code == 2
    assert probe_factory.configs == []
    assert fake_probe.calls == []
