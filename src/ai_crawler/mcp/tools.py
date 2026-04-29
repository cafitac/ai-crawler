"""MCP tool implementations independent of the MCP runtime package."""

from ai_crawler.sdk import AICrawler


class AICrawlerMCPTools:
    """Thin callable wrapper used by the stdio MCP server."""

    def __init__(self, crawler: AICrawler | None = None) -> None:
        self._crawler = crawler or AICrawler()

    def compile_url(
        self,
        url: str,
        goal: str = "collect data",
        evidence_path: str = "evidence.json",
        recipe_path: str = "recipe.yaml",
        repaired_recipe_path: str = "repaired.recipe.yaml",
        test_output_path: str = "test.jsonl",
        output_path: str = "crawl.jsonl",
        report_path: str = "auto.report.json",
        name: str = "generated-recipe",
    ) -> dict[str, object]:
        """Probe a target URL, compile a recipe, and return a harness-style report."""
        return self._crawler.compile_url(
            url=url,
            goal=goal,
            evidence_path=evidence_path,
            recipe_path=recipe_path,
            repaired_recipe_path=repaired_recipe_path,
            initial_output_path=test_output_path,
            final_output_path=output_path,
            report_path=report_path,
            name=name,
        ).report

    def auto_compile(
        self,
        evidence_path: str,
        recipe_path: str = "recipe.yaml",
        repaired_recipe_path: str = "repaired.recipe.yaml",
        test_output_path: str = "test.jsonl",
        output_path: str = "crawl.jsonl",
        report_path: str = "auto.report.json",
        name: str = "generated-recipe",
    ) -> dict[str, object]:
        """Generate, test, repair, and retest a crawler recipe from evidence JSON."""
        return self._crawler.auto(
            evidence_path=evidence_path,
            recipe_path=recipe_path,
            repaired_recipe_path=repaired_recipe_path,
            initial_output_path=test_output_path,
            final_output_path=output_path,
            report_path=report_path,
            name=name,
        ).report

    def generate_recipe(
        self,
        evidence_path: str,
        output_path: str = "recipe.yaml",
        name: str = "generated-recipe",
    ) -> dict[str, object]:
        """Generate a baseline recipe YAML from evidence JSON."""
        return self._crawler.generate_recipe(
            evidence_path=evidence_path,
            output_path=output_path,
            name=name,
        ).report

    def test_recipe(
        self,
        recipe_path: str = "recipe.yaml",
        output_path: str = "test.jsonl",
        report_path: str = "report.json",
    ) -> dict[str, object]:
        """Run one recipe test and return crawl/test report artifacts."""
        return self._crawler.test_recipe(
            recipe_path=recipe_path,
            output_path=output_path,
            report_path=report_path,
        ).report

    def repair_recipe(
        self,
        recipe_path: str = "recipe.yaml",
        report_path: str = "report.json",
        output_path: str = "repaired.recipe.yaml",
    ) -> dict[str, object]:
        """Repair a recipe using a test report JSON."""
        return self._crawler.repair_recipe(
            recipe_path=recipe_path,
            report_path=report_path,
            output_path=output_path,
        ).report
