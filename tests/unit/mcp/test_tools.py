"""MCP tool wrapper tests that avoid requiring the MCP runtime package."""

import json

from ai_crawler.core.models import FetchResponse, RequestSpec
from ai_crawler.mcp.tools import AICrawlerMCPTools
from ai_crawler.sdk import AICrawler


class ProductApiFetcher:
    def fetch(self, request: RequestSpec) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"items": [{"name": "Keyboard", "price": 120}]}),
            elapsed_ms=3,
        )


def test_mcp_auto_compile_tool_returns_harness_report(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
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
    tools = AICrawlerMCPTools(crawler=AICrawler(fetcher=ProductApiFetcher()))

    report = tools.auto_compile(
        evidence_path=str(evidence_path),
        recipe_path=str(tmp_path / "recipe.yaml"),
        repaired_recipe_path=str(tmp_path / "repaired.recipe.yaml"),
        test_output_path=str(tmp_path / "test.jsonl"),
        output_path=str(tmp_path / "crawl.jsonl"),
        report_path=str(tmp_path / "auto.report.json"),
        name="products-api",
    )

    assert report["ok"] is True
    assert report["command_type"] == "auto"
    assert report["failure_phase"] == ""
    assert [phase["name"] for phase in report["phase_diagnostics"]] == [
        "generate",
        "initial_test",
        "repair",
        "final_test",
    ]
    assert all(phase["status"] == "success" for phase in report["phase_diagnostics"])
    assert report["evidence_path"] == str(evidence_path.resolve())
    assert report["final_crawl_result"]["items_written"] == 1
    assert report["final_failure_classification"]["category"] == "success"
