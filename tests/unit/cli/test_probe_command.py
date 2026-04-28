"""CLI probe command tests."""

import importlib
import json

import pytest

from ai_crawler.core.models import EvidenceBundle, NetworkEvent

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
                    url="https://example.test/api/products?page=1",
                    status_code=200,
                    resource_type="fetch",
                ),
            ),
            observations=(
                "captured 1 raw browser network event(s)",
                "kept 1 replay candidate event(s)",
                "dropped 0 noise/static/error event(s)",
                "top candidate: GET https://example.test/api/products?page=1 status=200 type=fetch",
            ),
        )


class ProbeFactory:
    def __init__(self, probe: FakeProbe) -> None:
        self.probe = probe
        self.configs = []

    def __call__(self, config=None):
        self.configs.append(config)
        return self.probe


def test_probe_command_writes_evidence_json_with_defaults(tmp_path, capsys, monkeypatch) -> None:
    output_path = tmp_path / "evidence.json"
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)

    exit_code = cli_main.main(
        [
            "probe",
            "https://example.test/products",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert fake_probe.calls == [("https://example.test/products", "collect data")]
    assert capsys.readouterr().out.strip() == (
        f"ai-crawler probe: events=1 output={output_path}"
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {
        "target_url": "https://example.test/products",
        "goal": "collect data",
        "events": [
            {
                "method": "GET",
                "url": "https://example.test/api/products?page=1",
                "status_code": 200,
                "resource_type": "fetch",
            }
        ],
        "observations": [
            "captured 1 raw browser network event(s)",
            "kept 1 replay candidate event(s)",
            "dropped 0 noise/static/error event(s)",
            "top candidate: GET https://example.test/api/products?page=1 status=200 type=fetch",
        ],
        "redactions": [],
    }
    assert probe_factory.configs[0].include_resource_types == ("fetch", "xhr")
    assert probe_factory.configs[0].max_events == 200


def test_probe_command_accepts_custom_goal(tmp_path, capsys, monkeypatch) -> None:
    output_path = tmp_path / "evidence.json"
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)

    exit_code = cli_main.main(
        [
            "probe",
            "https://example.test/products",
            "--goal",
            "collect products",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert fake_probe.calls == [("https://example.test/products", "collect products")]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["goal"] == "collect products"
    assert "ai-crawler probe:" in capsys.readouterr().out


def test_probe_command_accepts_probe_tuning_options(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "evidence.json"
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)

    exit_code = cli_main.main(
        [
            "probe",
            "https://example.test/products",
            "--wait-ms",
            "2500",
            "--max-events",
            "7",
            "--include-resource-type",
            "document,xhr",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    config = probe_factory.configs[0]
    assert config.wait_after_load_ms == 2500
    assert config.max_events == 7
    assert config.include_resource_types == ("document", "xhr")


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--wait-ms", "-1"),
        ("--max-events", "0"),
        ("--include-resource-type", ""),
    ],
)
def test_probe_command_rejects_invalid_probe_tuning_options(
    option,
    value,
    tmp_path,
    monkeypatch,
) -> None:
    fake_probe = FakeProbe()
    probe_factory = ProbeFactory(fake_probe)
    monkeypatch.setattr(cli_main, "create_default_probe", probe_factory)

    with pytest.raises(SystemExit) as error:
        cli_main.main(
            [
                "probe",
                "https://example.test/products",
                option,
                value,
                "--output",
                str(tmp_path / "evidence.json"),
            ]
        )

    assert error.value.code == 2
    assert probe_factory.configs == []
    assert fake_probe.calls == []
