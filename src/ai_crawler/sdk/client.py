"""Thin application facade for CLI, MCP, and Python callers."""

from pathlib import Path
from typing import Any

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
from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.recipes import RecipeLoader
from ai_crawler.core.runner import RecipeFetcher

DEFAULT_RECIPE = "recipe.yaml"
DEFAULT_REPAIRED_RECIPE = "repaired.recipe.yaml"
DEFAULT_TEST_OUTPUT = "test.jsonl"
DEFAULT_RUN_OUTPUT = "crawl.jsonl"
DEFAULT_AUTO_REPORT = "auto.report.json"


class SDKResult(DomainModel):
    """Stable SDK return value for application wrappers."""

    ok: bool
    exit_code: int
    summary: str
    report: dict[str, Any]


class AICrawler:
    """Small public facade over ai-crawler core services."""

    def __init__(self, fetcher: RecipeFetcher | None = None) -> None:
        self._fetcher = fetcher or CurlCffiFetcher()
        self._evidence_loader = EvidenceLoader()

    def auto(
        self,
        evidence_path: Path | str,
        recipe_path: Path | str = DEFAULT_RECIPE,
        repaired_recipe_path: Path | str = DEFAULT_REPAIRED_RECIPE,
        initial_output_path: Path | str = DEFAULT_TEST_OUTPUT,
        final_output_path: Path | str = DEFAULT_RUN_OUTPUT,
        report_path: Path | str = DEFAULT_AUTO_REPORT,
        name: str = "generated-recipe",
    ) -> SDKResult:
        """Compile evidence into initial/repaired recipes and final crawl output."""
        evidence = self._evidence_loader.load_file(evidence_path)
        normalized_evidence = _resolve_path(evidence_path)
        normalized_recipe = _resolve_path(recipe_path)
        normalized_repaired = _resolve_path(repaired_recipe_path)
        normalized_initial_output = _resolve_path(initial_output_path)
        normalized_final_output = _resolve_path(final_output_path)
        normalized_report = _resolve_path(report_path)
        result = AutoRecipeCompiler(fetcher=self._fetcher).compile(
            evidence=evidence,
            recipe_name=name,
            initial_output_path=normalized_initial_output,
            final_output_path=normalized_final_output,
        )
        _write_recipe_yaml(recipe=result.recipe, output_path=normalized_recipe)
        _write_recipe_yaml(recipe=result.repaired_recipe, output_path=normalized_repaired)
        report = auto_report_payload(
            result=result,
            command_type="auto",
            recipe_path=normalized_recipe,
            repaired_recipe_path=normalized_repaired,
            output_path=normalized_final_output,
            evidence_path=normalized_evidence,
            failure_phase=_auto_failure_phase(result),
            phase_diagnostics=_auto_phase_diagnostics(result),
        )
        _write_json(report=report, output_path=normalized_report)
        return SDKResult(
            ok=result.ok,
            exit_code=auto_exit_code(result),
            summary=result.summary,
            report=report,
        )

    def generate_recipe(
        self,
        evidence_path: Path | str,
        output_path: Path | str = DEFAULT_RECIPE,
        name: str = "generated-recipe",
    ) -> SDKResult:
        """Generate and write a baseline recipe from evidence JSON."""
        evidence = self._evidence_loader.load_file(evidence_path)
        recipe = BaselineRecipeGenerator().generate(evidence=evidence, name=name)
        normalized_output = _resolve_path(output_path)
        _write_recipe_yaml(recipe=recipe, output_path=normalized_output)
        report = {
            "ok": True,
            "summary": f"generated recipe: {recipe.name}",
            "recipe_path": normalized_output,
            "recipe": recipe.model_dump(mode="json"),
        }
        summary = f"generated recipe: {recipe.name}"
        return SDKResult(ok=True, exit_code=0, summary=summary, report=report)

    def test_recipe(
        self,
        recipe_path: Path | str = DEFAULT_RECIPE,
        output_path: Path | str = DEFAULT_TEST_OUTPUT,
        report_path: Path | str = "report.json",
    ) -> SDKResult:
        """Test one recipe and write a diagnostic report."""
        recipe = RecipeLoader().load_file(recipe_path)
        normalized_output = _resolve_path(output_path)
        normalized_report = _resolve_path(report_path)
        result = TestRecipeTool(fetcher=self._fetcher)(
            AgentAction(
                name="test_recipe",
                arguments={
                    "recipe": recipe.model_dump(mode="json"),
                    "output_path": normalized_output,
                },
            ),
            EvidenceBundle(target_url=recipe.start_url, goal="test recipe"),
        )
        report = tool_report_payload(result)
        _write_json(report=report, output_path=normalized_report)
        return SDKResult(
            ok=result.ok,
            exit_code=0 if result.ok else 2,
            summary=result.summary,
            report=report,
        )

    def repair_recipe(
        self,
        recipe_path: Path | str = DEFAULT_RECIPE,
        report_path: Path | str = "report.json",
        output_path: Path | str = DEFAULT_REPAIRED_RECIPE,
    ) -> SDKResult:
        """Repair one recipe from a test report JSON."""
        recipe = RecipeLoader().load_file(recipe_path)
        report = _load_json_object(_resolve_path(report_path))
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
        normalized_output = _resolve_path(output_path)
        _write_recipe_yaml(recipe=repaired_recipe, output_path=normalized_output)
        payload = tool_report_payload(result)
        payload["repaired_recipe_path"] = normalized_output
        return SDKResult(
            ok=result.ok,
            exit_code=0 if result.ok else 2,
            summary=result.summary,
            report=payload,
        )

    def auto_from_evidence(
        self,
        evidence: EvidenceBundle,
        recipe_path: Path | str = DEFAULT_RECIPE,
        repaired_recipe_path: Path | str = DEFAULT_REPAIRED_RECIPE,
        initial_output_path: Path | str = DEFAULT_TEST_OUTPUT,
        final_output_path: Path | str = DEFAULT_RUN_OUTPUT,
        report_path: Path | str = DEFAULT_AUTO_REPORT,
        name: str = "generated-recipe",
    ) -> SDKResult:
        """Compile an in-memory evidence bundle for programmatic callers."""
        normalized_recipe = _resolve_path(recipe_path)
        normalized_repaired = _resolve_path(repaired_recipe_path)
        normalized_initial_output = _resolve_path(initial_output_path)
        normalized_final_output = _resolve_path(final_output_path)
        normalized_report = _resolve_path(report_path)
        result = AutoRecipeCompiler(fetcher=self._fetcher).compile(
            evidence=evidence,
            recipe_name=name,
            initial_output_path=normalized_initial_output,
            final_output_path=normalized_final_output,
        )
        _write_recipe_yaml(recipe=result.recipe, output_path=normalized_recipe)
        _write_recipe_yaml(recipe=result.repaired_recipe, output_path=normalized_repaired)
        report = auto_report_payload(
            result=result,
            command_type="auto",
            recipe_path=normalized_recipe,
            repaired_recipe_path=normalized_repaired,
            output_path=normalized_final_output,
            failure_phase=_auto_failure_phase(result),
            phase_diagnostics=_auto_phase_diagnostics(result),
        )
        _write_json(report=report, output_path=normalized_report)
        return SDKResult(
            ok=result.ok,
            exit_code=auto_exit_code(result),
            summary=result.summary,
            report=report,
        )


def auto_exit_code(result: AutoCompileResult) -> int:
    """Return process-style exit code for auto compile results."""
    if result.ok:
        return 0
    return 2


def auto_report_payload(
    result: AutoCompileResult,
    command_type: str,
    recipe_path: str,
    repaired_recipe_path: str,
    output_path: str,
    evidence_path: str | None = None,
    failure_phase: str = "",
    phase_diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Build the stable harness report payload."""
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


def _auto_failure_phase(result: AutoCompileResult) -> str:
    if result.ok:
        return ""
    return "final_test"


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


def tool_report_payload(result: ToolResult) -> dict[str, Any]:
    """Build a stable payload from one agent tool result."""
    return {
        "ok": result.ok,
        "summary": result.summary,
        **result.artifacts,
    }


def _resolve_path(path: Path | str) -> str:
    return str(Path(path).resolve())


def _write_recipe_yaml(recipe: Recipe, output_path: str) -> None:
    try:
        import yaml
    except ModuleNotFoundError as error:
        msg = "Install YAML support with `pip install pyyaml` or `uv sync`."
        raise RuntimeError(msg) from error

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(recipe.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def _write_json(report: dict[str, Any], output_path: str) -> None:
    import json

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json_object(path: str) -> dict[str, Any]:
    import json

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
