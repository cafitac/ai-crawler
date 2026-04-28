#!/usr/bin/env python3
"""Run a deterministic local MCP auto_compile smoke test.

This script uses the runtime-independent MCP tool wrapper against the local
fixture site. It exercises the same SDK/core path exposed by the stdio MCP
server while avoiding external network dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ai_crawler.mcp.tools import AICrawlerMCPTools
from ai_crawler.testing.fixture_site import FixtureSite


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    with FixtureSite(host=args.host, port=args.port) as site:
        evidence_path = workdir / "evidence.json"
        _write_evidence(evidence_path=evidence_path, base_url=site.base_url)

        report = AICrawlerMCPTools().auto_compile(
            evidence_path=str(evidence_path),
            recipe_path=str(workdir / "recipe.yaml"),
            repaired_recipe_path=str(workdir / "repaired.recipe.yaml"),
            test_output_path=str(workdir / "test.jsonl"),
            output_path=str(workdir / "crawl.jsonl"),
            report_path=str(workdir / "auto.report.json"),
            name=args.name,
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "mcp auto_compile smoke: "
            f"ok={report.get('ok')} "
            f"items_written={_items_written(report)} "
            f"report={workdir / 'auto.report.json'} "
            f"output={workdir / 'crawl.jsonl'}"
        )
    return 0 if report.get("ok") is True else 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ai-crawler MCP auto_compile against the local fixture site."
    )
    parser.add_argument(
        "--workdir",
        default=".tmp/mcp-auto-smoke",
        help="Directory for smoke-test evidence, recipes, reports, and crawl output.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Fixture bind host.")
    parser.add_argument(
        "--port",
        default=0,
        type=int,
        help="Fixture bind port; 0 picks a free port.",
    )
    parser.add_argument("--name", default="mcp-auto-smoke", help="Generated recipe name.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full machine report as JSON.",
    )
    return parser.parse_args(argv)


def _write_evidence(evidence_path: Path, base_url: str) -> None:
    evidence: dict[str, Any] = {
        "target_url": f"{base_url}/products",
        "goal": "collect fixture products",
        "events": [
            {
                "method": "GET",
                "url": f"{base_url}/api/products?page=1",
                "status_code": 200,
                "resource_type": "fetch",
            }
        ],
    }
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def _items_written(report: dict[str, object]) -> object:
    final_result = report.get("final_crawl_result")
    if isinstance(final_result, dict):
        return final_result.get("items_written", "")
    return ""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
