"""CLI probe command tests."""

import importlib
import json

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
            observations=("captured 1 browser network event(s)",),
        )


def test_probe_command_writes_evidence_json_with_defaults(tmp_path, capsys, monkeypatch) -> None:
    output_path = tmp_path / "evidence.json"
    fake_probe = FakeProbe()
    monkeypatch.setattr(cli_main, "create_default_probe", lambda: fake_probe)

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
        "observations": ["captured 1 browser network event(s)"],
        "redactions": [],
    }


def test_probe_command_accepts_custom_goal(tmp_path, capsys, monkeypatch) -> None:
    output_path = tmp_path / "evidence.json"
    fake_probe = FakeProbe()
    monkeypatch.setattr(cli_main, "create_default_probe", lambda: fake_probe)

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
