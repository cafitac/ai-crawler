"""Deterministic end-to-end auto recipe compilation."""

from ai_crawler.core.agent.recipe_generation import BaselineRecipeGenerator
from ai_crawler.core.agent.recipe_repair import RepairRecipeTool
from ai_crawler.core.agent.recipe_testing import TestRecipeTool
from ai_crawler.core.diagnostics import classify_test_report
from ai_crawler.core.models import AgentAction, CrawlResult, EvidenceBundle, Recipe, ToolResult
from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.runner import RecipeFetcher


class AutoCompileResult(DomainModel):
    """Machine-readable result from the deterministic auto compiler."""

    ok: bool
    recipe: Recipe
    repaired_recipe: Recipe
    initial_crawl_result: CrawlResult
    final_crawl_result: CrawlResult
    initial_test_report: dict[str, object]
    final_test_report: dict[str, object]
    initial_failure_classification: dict[str, object]
    final_failure_classification: dict[str, object]
    summary: str


class AutoRecipeCompiler:
    """Run generate -> test -> repair -> test with deterministic tools."""

    def __init__(
        self,
        fetcher: RecipeFetcher,
        generator: BaselineRecipeGenerator | None = None,
        repair_tool: RepairRecipeTool | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._generator = generator or BaselineRecipeGenerator()
        self._repair_tool = repair_tool or RepairRecipeTool()

    def compile(
        self,
        evidence: EvidenceBundle,
        recipe_name: str,
        initial_output_path: str,
        final_output_path: str,
    ) -> AutoCompileResult:
        """Compile evidence into a repaired recipe and final crawl artifact."""
        recipe = self._generator.generate(evidence=evidence, name=recipe_name)
        initial_test = self._test_recipe(
            recipe=recipe,
            evidence=evidence,
            output_path=initial_output_path,
        )
        repaired_recipe = self._repair_recipe(
            recipe=recipe,
            evidence=evidence,
            initial_test=initial_test,
        )
        final_test = self._test_recipe(
            recipe=repaired_recipe,
            evidence=evidence,
            output_path=final_output_path,
        )
        initial_test_report = _test_report(initial_test)
        final_test_report = _test_report(final_test)
        initial_classification = classify_test_report(initial_test_report)
        final_classification = classify_test_report(final_test_report)
        final_crawl_result = _crawl_result(final_test)
        ok = final_test.ok and final_classification["category"] == "success"
        return AutoCompileResult(
            ok=ok,
            recipe=recipe,
            repaired_recipe=repaired_recipe,
            initial_crawl_result=_crawl_result(initial_test),
            final_crawl_result=final_crawl_result,
            initial_test_report=initial_test_report,
            final_test_report=final_test_report,
            initial_failure_classification=initial_classification,
            final_failure_classification=final_classification,
            summary=(
                f"auto compiled recipe: {repaired_recipe.name} "
                f"items_written={final_crawl_result.items_written}"
            ),
        )

    def _test_recipe(
        self,
        recipe: Recipe,
        evidence: EvidenceBundle,
        output_path: str,
    ) -> ToolResult:
        return TestRecipeTool(fetcher=self._fetcher)(
            AgentAction(
                name="test_recipe",
                arguments={"recipe": recipe.model_dump(mode="json"), "output_path": output_path},
            ),
            evidence,
        )

    def _repair_recipe(
        self,
        recipe: Recipe,
        evidence: EvidenceBundle,
        initial_test: ToolResult,
    ) -> Recipe:
        repair_result = self._repair_tool(
            AgentAction(
                name="repair_recipe",
                arguments={
                    "recipe": recipe.model_dump(mode="json"),
                    "crawl_result": _artifact_dict(initial_test, "crawl_result"),
                    "test_report": _artifact_dict(initial_test, "test_report"),
                },
            ),
            evidence,
        )
        artifact = _artifact_dict(repair_result, "recipe")
        if repair_result.ok and artifact:
            return Recipe.model_validate(artifact)
        return recipe


def _crawl_result(result: ToolResult) -> CrawlResult:
    artifact = _artifact_dict(result, "crawl_result")
    return CrawlResult.model_validate(artifact)


def _test_report(result: ToolResult) -> dict[str, object]:
    return _artifact_dict(result, "test_report")


def _artifact_dict(result: ToolResult, key: str) -> dict[str, object]:
    artifact = result.artifacts.get(key, {})
    if isinstance(artifact, dict):
        return artifact
    return {}
