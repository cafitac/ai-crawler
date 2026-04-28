import subprocess
import sys


def test_cli_help_exits_successfully() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ai_crawler.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "ai-crawler" in result.stdout
    assert "doctor" in result.stdout
    assert "probe" in result.stdout
    assert "run" in result.stdout
    assert "generate-recipe" in result.stdout
    assert "test-recipe" in result.stdout
    assert "repair-recipe" in result.stdout
    assert "auto" in result.stdout
    assert "mcp" in result.stdout
    assert "mcp-config" in result.stdout
