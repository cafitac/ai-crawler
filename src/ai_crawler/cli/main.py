"""CLI entrypoint for ai-crawler."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ai_crawler import __version__
from ai_crawler.adapters.browser import BrowserProbeConfig, PlaywrightNetworkProbe
from ai_crawler.adapters.http import CurlCffiFetcher
from ai_crawler.core.agent import (
    AutoCompileResult,
    AutoRecipeCompiler,
    BaselineRecipeGenerator,
    RepairRecipeTool,
    TestRecipeTool,
)
from ai_crawler.core.evidence import EvidenceLoader
from ai_crawler.core.models import AgentAction, EvidenceBundle, Recipe, ToolResult
from ai_crawler.core.recipes import RecipeLoader
from ai_crawler.core.runner import RecipeFetcher, RecipeRunner, RunnerConfig
from ai_crawler.core.security import redact_text
from ai_crawler.mcp.config import (
    SUPPORTED_CLIENTS,
    SUPPORTED_LAUNCHERS,
    build_client_config,
)

DEFAULT_RUN_OUTPUT = "crawl.jsonl"
DEFAULT_EVIDENCE_OUTPUT = "evidence.json"
DEFAULT_GENERATED_RECIPE = "recipe.yaml"
DEFAULT_TEST_OUTPUT = "test.jsonl"
DEFAULT_TEST_REPORT = "report.json"
DEFAULT_REPAIRED_RECIPE = "repaired.recipe.yaml"
DEFAULT_AUTO_REPORT = "auto.report.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-crawler",
        description="AI-powered network-first crawler compiler.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ai-crawler {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "doctor",
        help="Check local ai-crawler environment readiness.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    probe_parser = subparsers.add_parser(
        "probe",
        help="Open a target briefly in a browser and write network evidence JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    probe_parser.add_argument("url", help="Target page URL to inspect with a short browser probe.")
    probe_parser.add_argument(
        "--goal",
        default="collect data",
        help="Human goal to include in the evidence bundle.",
    )
    probe_parser.add_argument(
        "--output",
        default=DEFAULT_EVIDENCE_OUTPUT,
        help="Path to write EvidenceBundle JSON.",
    )
    _add_probe_tuning_options(probe_parser)

    compile_parser = subparsers.add_parser(
        "compile",
        help="Probe a URL, generate, test, repair, and retest in one command.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    compile_parser.add_argument("url", help="Target page URL to probe and compile.")
    compile_parser.add_argument(
        "--goal",
        default="collect data",
        help="Human goal to include in generated evidence.",
    )
    compile_parser.add_argument(
        "--evidence",
        default=DEFAULT_EVIDENCE_OUTPUT,
        help="Path to write browser probe evidence JSON.",
    )
    compile_parser.add_argument(
        "--recipe",
        default=DEFAULT_GENERATED_RECIPE,
        help="Path to write the initial generated recipe YAML.",
    )
    compile_parser.add_argument(
        "--repaired-recipe",
        default=DEFAULT_REPAIRED_RECIPE,
        help="Path to write the repaired recipe YAML.",
    )
    compile_parser.add_argument(
        "--test-output",
        default=DEFAULT_TEST_OUTPUT,
        help="Path to write the initial test JSON Lines output.",
    )
    compile_parser.add_argument(
        "--output",
        default=DEFAULT_RUN_OUTPUT,
        help="Path to write final JSON Lines crawl output.",
    )
    compile_parser.add_argument(
        "--report",
        default=DEFAULT_AUTO_REPORT,
        help="Path to write the final auto report JSON.",
    )
    compile_parser.add_argument(
        "--name",
        default="generated-recipe",
        help="Recipe name to write into generated artifacts.",
    )
    compile_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final compile report JSON to stdout for AI harnesses.",
    )
    _add_probe_tuning_options(compile_parser)

    run_parser = subparsers.add_parser(
        "run",
        help="Run a validated crawler recipe.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    run_parser.add_argument("recipe", help="Path to a recipe YAML file.")
    run_parser.add_argument(
        "--output",
        default=DEFAULT_RUN_OUTPUT,
        help="Path to write JSON Lines crawl output.",
    )

    generate_parser = subparsers.add_parser(
        "generate-recipe",
        help="Generate a baseline recipe from evidence JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    generate_parser.add_argument("evidence", help="Path to an EvidenceBundle JSON file.")
    generate_parser.add_argument(
        "--output",
        default=DEFAULT_GENERATED_RECIPE,
        help="Path to write the generated recipe YAML.",
    )
    generate_parser.add_argument(
        "--name",
        default="generated-recipe",
        help="Recipe name to write into the generated recipe.",
    )

    test_parser = subparsers.add_parser(
        "test-recipe",
        help="Test a recipe and write crawl/test report artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    test_parser.add_argument("recipe", help="Path to a recipe YAML file.")
    test_parser.add_argument(
        "--output",
        default=DEFAULT_TEST_OUTPUT,
        help="Path to write JSON Lines test crawl output.",
    )
    test_parser.add_argument(
        "--report",
        default=DEFAULT_TEST_REPORT,
        help="Path to write JSON test report artifacts.",
    )

    repair_parser = subparsers.add_parser(
        "repair-recipe",
        help="Repair a recipe from one test report JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    repair_parser.add_argument("recipe", help="Path to a recipe YAML file.")
    repair_parser.add_argument(
        "--report",
        default=DEFAULT_TEST_REPORT,
        help="Path to the JSON report written by test-recipe.",
    )
    repair_parser.add_argument(
        "--output",
        default=DEFAULT_REPAIRED_RECIPE,
        help="Path to write the repaired recipe YAML.",
    )

    auto_parser = subparsers.add_parser(
        "auto",
        help="Generate, test, repair, and retest from evidence JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    auto_parser.add_argument("evidence", help="Path to an EvidenceBundle JSON file.")
    auto_parser.add_argument(
        "--recipe",
        default=DEFAULT_GENERATED_RECIPE,
        help="Path to write the initial generated recipe YAML.",
    )
    auto_parser.add_argument(
        "--repaired-recipe",
        default=DEFAULT_REPAIRED_RECIPE,
        help="Path to write the repaired recipe YAML.",
    )
    auto_parser.add_argument(
        "--test-output",
        default=DEFAULT_TEST_OUTPUT,
        help="Path to write the initial test JSON Lines output.",
    )
    auto_parser.add_argument(
        "--output",
        default=DEFAULT_RUN_OUTPUT,
        help="Path to write final JSON Lines crawl output.",
    )
    auto_parser.add_argument(
        "--report",
        default=DEFAULT_AUTO_REPORT,
        help="Path to write the final auto report JSON.",
    )
    auto_parser.add_argument(
        "--name",
        default="generated-recipe",
        help="Recipe name to write into generated artifacts.",
    )
    auto_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final auto report JSON to stdout for AI harnesses.",
    )

    subparsers.add_parser(
        "mcp",
        help="Run ai-crawler as a stdio MCP server.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    mcp_config_parser = subparsers.add_parser(
        "mcp-config",
        help="Print MCP client config snippets for Hermes, Claude Code, or Codex.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    mcp_config_parser.add_argument(
        "--client",
        choices=SUPPORTED_CLIENTS,
        required=True,
        help="MCP client to configure.",
    )
    mcp_config_parser.add_argument(
        "--project",
        default=".",
        help="Path to the ai-crawler project root for uv --project.",
    )
    mcp_config_parser.add_argument(
        "--launcher",
        choices=SUPPORTED_LAUNCHERS,
        default="uv",
        help="Launcher to use in the generated MCP snippet.",
    )
    return parser


def _add_probe_tuning_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--wait-ms",
        type=_non_negative_int,
        default=1_000,
        help="Milliseconds to wait after browser network idle during probe.",
    )
    parser.add_argument(
        "--max-events",
        type=_positive_int,
        default=200,
        help="Maximum replay candidate events to keep after probe filtering.",
    )
    parser.add_argument(
        "--include-resource-type",
        type=_non_empty_csv,
        default="fetch,xhr",
        help="Comma-separated browser resource types to keep as replay candidates.",
    )


def _probe_config_from_args(args: argparse.Namespace) -> BrowserProbeConfig:
    return BrowserProbeConfig(
        wait_after_load_ms=args.wait_ms,
        max_events=args.max_events,
        include_resource_types=_parse_csv_tuple(args.include_resource_type),
    )


def _parse_csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _non_negative_int(value: str) -> int:
    parsed = _parse_int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def _positive_int(value: str) -> int:
    parsed = _parse_int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than or equal to 1")
    return parsed


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error


def _non_empty_csv(value: str) -> str:
    if not _parse_csv_tuple(value):
        raise argparse.ArgumentTypeError("must include at least one value")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print("ai-crawler doctor: ok")
        return 0

    if args.command == "run":
        return run_recipe_command(recipe_path=args.recipe, output_path=args.output)

    if args.command == "probe":
        return probe_command(
            url=args.url,
            goal=args.goal,
            output_path=args.output,
            probe_config=_probe_config_from_args(args),
        )

    if args.command == "compile":
        return compile_command(
            url=args.url,
            goal=args.goal,
            evidence_path=args.evidence,
            recipe_path=args.recipe,
            repaired_recipe_path=args.repaired_recipe,
            initial_output_path=args.test_output,
            final_output_path=args.output,
            report_path=args.report,
            name=args.name,
            json_output=args.json,
            probe_config=_probe_config_from_args(args),
        )

    if args.command == "generate-recipe":
        return generate_recipe_command(
            evidence_path=args.evidence,
            output_path=args.output,
            name=args.name,
        )

    if args.command == "test-recipe":
        return test_recipe_command(
            recipe_path=args.recipe,
            output_path=args.output,
            report_path=args.report,
        )

    if args.command == "repair-recipe":
        return repair_recipe_command(
            recipe_path=args.recipe,
            report_path=args.report,
            output_path=args.output,
        )

    if args.command == "auto":
        return auto_command(
            evidence_path=args.evidence,
            recipe_path=args.recipe,
            repaired_recipe_path=args.repaired_recipe,
            initial_output_path=args.test_output,
            final_output_path=args.output,
            report_path=args.report,
            name=args.name,
            json_output=args.json,
        )

    if args.command == "mcp":
        return mcp_command()

    if args.command == "mcp-config":
        return mcp_config_command(
            client=args.client,
            project_path=args.project,
            launcher=args.launcher,
        )

    return 0


def mcp_command() -> int:
    """Run the stdio MCP server."""
    from ai_crawler.mcp.server import run_stdio_server

    run_stdio_server()
    return 0


def mcp_config_command(
    client: str,
    project_path: str,
    launcher: str = "uv",
) -> int:
    """Print a ready-to-paste MCP client snippet."""
    print(build_client_config(client=client, project_path=project_path, launcher=launcher))
    return 0


def probe_command(
    url: str,
    goal: str,
    output_path: str,
    probe_config: BrowserProbeConfig | None = None,
) -> int:
    """Capture browser network evidence and write an EvidenceBundle JSON file."""
    evidence = create_default_probe(config=probe_config).probe(url=url, goal=goal)
    _write_evidence_json(evidence=evidence, output_path=output_path)
    print(f"ai-crawler probe: events={len(evidence.events)} output={output_path}")
    return 0


def compile_command(
    url: str,
    goal: str,
    evidence_path: str,
    recipe_path: str,
    repaired_recipe_path: str,
    initial_output_path: str,
    final_output_path: str,
    report_path: str,
    name: str,
    json_output: bool = False,
    probe_config: BrowserProbeConfig | None = None,
) -> int:
    """Probe a URL and run the deterministic auto compiler from captured evidence."""
    normalized_evidence_path = str(Path(evidence_path).resolve())
    normalized_recipe_path = str(Path(recipe_path).resolve())
    normalized_repaired_path = str(Path(repaired_recipe_path).resolve())
    normalized_initial_output = str(Path(initial_output_path).resolve())
    normalized_final_output = str(Path(final_output_path).resolve())
    normalized_report_path = str(Path(report_path).resolve())
    try:
        evidence = create_default_probe(config=probe_config).probe(url=url, goal=goal)
    except Exception as error:
        report = _write_compile_failure_report(
            report_path=normalized_report_path,
            url=url,
            goal=goal,
            evidence_path=normalized_evidence_path,
            recipe_path=normalized_recipe_path,
            repaired_recipe_path=normalized_repaired_path,
            output_path=normalized_final_output,
            failure_phase="probe",
            summary=_probe_failure_summary(error),
            phase_diagnostics=[
                {
                    "name": "probe",
                    "status": "failed",
                    "summary": _probe_failure_summary(error),
                }
            ],
            failure_classification={
                "category": "probe_failed",
                "retryable": True,
                "requires_human": False,
            },
        )
        return _emit_compile_failure(report=report, json_output=json_output)

    _write_evidence_json(evidence=evidence, output_path=normalized_evidence_path)
    try:
        result = AutoRecipeCompiler(fetcher=create_default_fetcher()).compile(
            evidence=evidence,
            recipe_name=name,
            initial_output_path=normalized_initial_output,
            final_output_path=normalized_final_output,
        )
    except ValueError as error:
        if "no endpoint candidates" not in str(error):
            raise
        summary = _no_endpoint_candidates_summary()
        report = _write_compile_failure_report(
            report_path=normalized_report_path,
            url=url,
            goal=goal,
            evidence_path=normalized_evidence_path,
            recipe_path=normalized_recipe_path,
            repaired_recipe_path=normalized_repaired_path,
            output_path=normalized_final_output,
            failure_phase="generate",
            summary=summary,
            phase_diagnostics=[
                _probe_phase_diagnostic(evidence),
                {
                    "name": "generate",
                    "status": "failed",
                    "summary": summary,
                },
            ],
            failure_classification={
                "category": "no_endpoint_candidates",
                "retryable": True,
                "requires_human": False,
            },
        )
        return _emit_compile_failure(report=report, json_output=json_output)
    _write_recipe_yaml(recipe=result.recipe, output_path=normalized_recipe_path)
    _write_recipe_yaml(recipe=result.repaired_recipe, output_path=normalized_repaired_path)
    report = _write_auto_report(
        result=result,
        report_path=normalized_report_path,
        recipe_path=normalized_recipe_path,
        repaired_recipe_path=normalized_repaired_path,
        output_path=normalized_final_output,
        evidence_path=normalized_evidence_path,
        command_type="compile",
        failure_phase=_auto_failure_phase(result),
        phase_diagnostics=_compile_phase_diagnostics(evidence=evidence, result=result),
    )
    if json_output:
        print(json.dumps(report, ensure_ascii=False))
        return _auto_exit_code(result)
    print(
        "ai-crawler compile: "
        f"recipe={result.repaired_recipe.name} "
        f"items_written={result.final_crawl_result.items_written} "
        f"evidence={normalized_evidence_path} "
        f"output={normalized_final_output} "
        f"report={normalized_report_path}"
    )
    return _auto_exit_code(result)


def run_recipe_command(recipe_path: str, output_path: str) -> int:
    """Load and run one recipe file from the CLI."""
    recipe = RecipeLoader().load_file(recipe_path)
    runner = RecipeRunner(
        fetcher=create_default_fetcher(),
        config=RunnerConfig(output_path=output_path),
    )
    result = runner.run(recipe)
    checkpoint_summary = (
        f" checkpoint={result.checkpoint_path}"
        if result.checkpoint_path
        else ""
    )
    summary = (
        "ai-crawler run: "
        f"recipe={result.recipe_name} "
        f"items_written={result.items_written} "
        f"pages_scheduled={result.pages_scheduled} "
        f"pages_completed={result.pages_completed} "
        f"pages_failed={result.pages_failed} "
        f"pages_attempted={result.pages_attempted} "
        f"requests_attempted={result.requests_attempted} "
        f"stop_reason={result.stop_reason} "
        f"output={output_path}"
        f"{checkpoint_summary}"
    )
    print(summary)
    return 0


def generate_recipe_command(evidence_path: str, output_path: str, name: str) -> int:
    """Generate a baseline recipe from an EvidenceBundle JSON file."""
    evidence = EvidenceLoader().load_file(evidence_path)
    recipe = BaselineRecipeGenerator().generate(evidence=evidence, name=name)
    _write_recipe_yaml(recipe=recipe, output_path=output_path)
    print(f"ai-crawler generate-recipe: recipe={recipe.name} output={output_path}")
    return 0


def test_recipe_command(recipe_path: str, output_path: str, report_path: str) -> int:
    """Test one recipe and write diagnostic report artifacts."""
    recipe = RecipeLoader().load_file(recipe_path)
    result = TestRecipeTool(fetcher=create_default_fetcher())(
        AgentAction(
            name="test_recipe",
            arguments={"recipe": recipe.model_dump(mode="json"), "output_path": output_path},
        ),
        EvidenceBundle(target_url=recipe.start_url, goal="test recipe"),
    )
    _write_tool_report(result=result, report_path=report_path)
    crawl_result = _artifact_dict(result, "crawl_result")
    test_report = _artifact_dict(result, "test_report")
    summary = (
        "ai-crawler test-recipe: "
        f"recipe={crawl_result.get('recipe_name', recipe.name)} "
        f"items_written={crawl_result.get('items_written', 0)} "
        f"pages_scheduled={crawl_result.get('pages_scheduled', 0)} "
        f"pages_completed={crawl_result.get('pages_completed', 0)} "
        f"pages_failed={crawl_result.get('pages_failed', 0)} "
        f"failure_reason={test_report.get('failure_reason', '')} "
        f"output={output_path} "
        f"report={report_path}"
    )
    print(summary)
    return 0

def repair_recipe_command(recipe_path: str, report_path: str, output_path: str) -> int:
    """Repair one recipe using the single JSON report written by test-recipe."""
    normalized_report_path = str(Path(report_path).resolve())
    normalized_output_path = str(Path(output_path).resolve())
    recipe = RecipeLoader().load_file(recipe_path)
    report = _load_json_object(normalized_report_path)
    result = RepairRecipeTool()(
        AgentAction(
            name="repair_recipe",
            arguments={
                "recipe": recipe.model_dump(mode="json"),
                "crawl_result": report.get("crawl_result", {}),
                "test_report": report.get("test_report", {}),
            },
        ),
        EvidenceBundle(target_url=recipe.start_url, goal="repair recipe"),
    )
    repaired_recipe = _recipe_from_tool_result(result=result, fallback=recipe)
    _write_recipe_yaml(recipe=repaired_recipe, output_path=normalized_output_path)
    print(
        "ai-crawler repair-recipe: "
        f"recipe={repaired_recipe.name} "
        f"output={normalized_output_path} "
        f"report={normalized_report_path}"
    )
    return 0


def auto_command(
    evidence_path: str,
    recipe_path: str,
    repaired_recipe_path: str,
    initial_output_path: str,
    final_output_path: str,
    report_path: str,
    name: str,
    json_output: bool = False,
) -> int:
    """Run the one-command deterministic AI harness flow."""
    normalized_recipe_path = str(Path(recipe_path).resolve())
    normalized_repaired_path = str(Path(repaired_recipe_path).resolve())
    normalized_initial_output = str(Path(initial_output_path).resolve())
    normalized_final_output = str(Path(final_output_path).resolve())
    normalized_report_path = str(Path(report_path).resolve())
    evidence = EvidenceLoader().load_file(evidence_path)
    result = AutoRecipeCompiler(fetcher=create_default_fetcher()).compile(
        evidence=evidence,
        recipe_name=name,
        initial_output_path=normalized_initial_output,
        final_output_path=normalized_final_output,
    )
    _write_recipe_yaml(recipe=result.recipe, output_path=normalized_recipe_path)
    _write_recipe_yaml(recipe=result.repaired_recipe, output_path=normalized_repaired_path)
    report = _write_auto_report(
        result=result,
        report_path=normalized_report_path,
        recipe_path=normalized_recipe_path,
        repaired_recipe_path=normalized_repaired_path,
        output_path=normalized_final_output,
        command_type="auto",
        failure_phase=_auto_failure_phase(result),
        phase_diagnostics=_auto_phase_diagnostics(result),
    )
    if json_output:
        print(json.dumps(report, ensure_ascii=False))
        return _auto_exit_code(result)
    print(
        "ai-crawler auto: "
        f"recipe={result.repaired_recipe.name} "
        f"items_written={result.final_crawl_result.items_written} "
        f"output={normalized_final_output} "
        f"report={normalized_report_path}"
    )
    return _auto_exit_code(result)


def _auto_exit_code(result: AutoCompileResult) -> int:
    if result.ok:
        return 0
    return 2


def _write_recipe_yaml(recipe: Recipe, output_path: str) -> None:
    try:
        import yaml
    except ModuleNotFoundError as error:
        msg = "Install YAML support with `pip install pyyaml` or `uv sync`."
        raise RuntimeError(msg) from error

    recipe_path = Path(output_path)
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(
        yaml.safe_dump(recipe.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def _write_tool_report(result: ToolResult, report_path: str) -> None:
    report = {
        "ok": result.ok,
        "summary": result.summary,
        **result.artifacts,
    }
    output_path = Path(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_evidence_json(evidence: EvidenceBundle, output_path: str) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_auto_report(
    result: AutoCompileResult,
    report_path: str,
    recipe_path: str,
    repaired_recipe_path: str,
    output_path: str,
    evidence_path: str | None = None,
    command_type: str = "auto",
    failure_phase: str = "",
    phase_diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    report = _auto_report_payload(
        result=result,
        recipe_path=recipe_path,
        repaired_recipe_path=repaired_recipe_path,
        output_path=output_path,
        evidence_path=evidence_path,
        command_type=command_type,
        failure_phase=failure_phase,
        phase_diagnostics=phase_diagnostics or _auto_phase_diagnostics(result),
    )
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _auto_report_payload(
    result: AutoCompileResult,
    recipe_path: str,
    repaired_recipe_path: str,
    output_path: str,
    evidence_path: str | None = None,
    command_type: str = "auto",
    failure_phase: str = "",
    phase_diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    report = {
        "ok": result.ok,
        "command_type": command_type,
        "failure_phase": failure_phase,
        "phase_diagnostics": phase_diagnostics or _auto_phase_diagnostics(result),
        "summary": result.summary,
        "recipe_path": recipe_path,
        "repaired_recipe_path": repaired_recipe_path,
        "output_path": output_path,
        "initial_crawl_result": result.initial_crawl_result.model_dump(mode="json"),
        "final_crawl_result": result.final_crawl_result.model_dump(mode="json"),
        "initial_test_report": result.initial_test_report,
        "final_test_report": result.final_test_report,
        "initial_failure_classification": result.initial_failure_classification,
        "final_failure_classification": result.final_failure_classification,
    }
    if evidence_path is not None:
        report["evidence_path"] = evidence_path
    return report


def _write_compile_failure_report(
    report_path: str,
    url: str,
    goal: str,
    evidence_path: str,
    recipe_path: str,
    repaired_recipe_path: str,
    output_path: str,
    failure_phase: str,
    summary: str,
    phase_diagnostics: list[dict[str, object]],
    failure_classification: dict[str, object],
) -> dict[str, Any]:
    report = {
        "ok": False,
        "command_type": "compile",
        "target_url": url,
        "goal": goal,
        "failure_phase": failure_phase,
        "failure_classification": failure_classification,
        "phase_diagnostics": phase_diagnostics,
        "summary": summary,
        "evidence_path": evidence_path,
        "recipe_path": recipe_path,
        "repaired_recipe_path": repaired_recipe_path,
        "output_path": output_path,
    }
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _emit_compile_failure(report: dict[str, Any], json_output: bool) -> int:
    print(f"ai-crawler compile failed: {report['summary']}", file=sys.stderr)
    if json_output:
        print(json.dumps(report, ensure_ascii=False))
    return 2


def _compile_phase_diagnostics(
    evidence: EvidenceBundle,
    result: AutoCompileResult,
) -> list[dict[str, object]]:
    return [_probe_phase_diagnostic(evidence), *_auto_phase_diagnostics(result)]


def _auto_phase_diagnostics(result: AutoCompileResult) -> list[dict[str, object]]:
    return [
        {
            "name": "generate",
            "status": "success",
            "summary": f"generated initial recipe: {result.recipe.name}",
        },
        {
            "name": "initial_test",
            "status": "success",
            "summary": _test_phase_summary(result.initial_test_report),
        },
        {
            "name": "repair",
            "status": "success",
            "summary": f"selected final recipe: {result.repaired_recipe.name}",
        },
        {
            "name": "final_test",
            "status": "success" if result.ok else "failed",
            "summary": _test_phase_summary(result.final_test_report),
        },
    ]


def _auto_failure_phase(result: AutoCompileResult) -> str:
    if result.ok:
        return ""
    return "final_test"


def _probe_phase_diagnostic(evidence: EvidenceBundle) -> dict[str, object]:
    return {
        "name": "probe",
        "status": "success",
        "summary": f"captured {len(evidence.events)} network event(s)",
    }


def _test_phase_summary(test_report: dict[str, object]) -> str:
    classification = test_report.get("failure_classification", {})
    category = "unknown"
    if isinstance(classification, dict):
        raw_category = classification.get("category", "unknown")
        if isinstance(raw_category, str) and raw_category:
            category = raw_category
    failure_reason = test_report.get("failure_reason", "")
    if isinstance(failure_reason, str) and failure_reason:
        return f"classification={category} reason={failure_reason}"
    return f"classification={category}"


def _probe_failure_summary(error: Exception) -> str:
    message = redact_text(str(error))
    if message:
        return f"browser probe failed: {message}"
    return "browser probe failed; install browser support and verify the target is reachable"


def _no_endpoint_candidates_summary() -> str:
    return (
        "no useful network endpoint candidates were captured; inspect evidence or retry probe "
        "with an authorized target"
    )


def _load_json_object(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    msg = f"Expected JSON object in report file: {path}"
    raise ValueError(msg)


def _recipe_from_tool_result(result: ToolResult, fallback: Recipe) -> Recipe:
    artifact = result.artifacts.get("recipe")
    if not result.ok or not isinstance(artifact, dict):
        return fallback
    return Recipe.model_validate(artifact)


def _artifact_dict(result: ToolResult, key: str) -> dict[str, Any]:
    artifact = result.artifacts.get(key, {})
    if isinstance(artifact, dict):
        return artifact
    return {}


def create_default_fetcher() -> RecipeFetcher:
    """Create the default network-first HTTP fetcher for CLI runs."""
    return CurlCffiFetcher()


def create_default_probe(config: BrowserProbeConfig | None = None) -> PlaywrightNetworkProbe:
    """Create the default short browser probe for evidence discovery."""
    return PlaywrightNetworkProbe(config=config or BrowserProbeConfig())
