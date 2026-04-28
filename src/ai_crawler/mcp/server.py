"""Stdio MCP server entrypoint."""

from ai_crawler.mcp.tools import AICrawlerMCPTools


def build_server():
    """Build the MCP server lazily so the base package does not require mcp."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as error:
        msg = "Install MCP support with `uv sync --extra mcp` or `pip install ai-crawler[mcp]`."
        raise RuntimeError(msg) from error

    app = FastMCP("ai-crawler")
    tools = AICrawlerMCPTools()

    @app.tool()
    def auto_compile(
        evidence_path: str,
        recipe_path: str = "recipe.yaml",
        repaired_recipe_path: str = "repaired.recipe.yaml",
        test_output_path: str = "test.jsonl",
        output_path: str = "crawl.jsonl",
        report_path: str = "auto.report.json",
        name: str = "generated-recipe",
    ) -> dict[str, object]:
        """Generate, test, repair, and retest a recipe from evidence JSON."""
        return tools.auto_compile(
            evidence_path=evidence_path,
            recipe_path=recipe_path,
            repaired_recipe_path=repaired_recipe_path,
            test_output_path=test_output_path,
            output_path=output_path,
            report_path=report_path,
            name=name,
        )

    @app.tool()
    def generate_recipe(
        evidence_path: str,
        output_path: str = "recipe.yaml",
        name: str = "generated-recipe",
    ) -> dict[str, object]:
        """Generate a baseline recipe YAML from evidence JSON."""
        return tools.generate_recipe(
            evidence_path=evidence_path,
            output_path=output_path,
            name=name,
        )

    @app.tool()
    def test_recipe(
        recipe_path: str = "recipe.yaml",
        output_path: str = "test.jsonl",
        report_path: str = "report.json",
    ) -> dict[str, object]:
        """Run a recipe test and return crawl/test report artifacts."""
        return tools.test_recipe(
            recipe_path=recipe_path,
            output_path=output_path,
            report_path=report_path,
        )

    @app.tool()
    def repair_recipe(
        recipe_path: str = "recipe.yaml",
        report_path: str = "report.json",
        output_path: str = "repaired.recipe.yaml",
    ) -> dict[str, object]:
        """Repair a recipe using one test report JSON."""
        return tools.repair_recipe(
            recipe_path=recipe_path,
            report_path=report_path,
            output_path=output_path,
        )

    return app


def run_stdio_server() -> None:
    """Run ai-crawler as a stdio MCP server."""
    build_server().run()
