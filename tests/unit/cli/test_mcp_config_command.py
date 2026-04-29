"""CLI mcp-config command tests."""

import importlib

cli_main = importlib.import_module("ai_crawler.cli.main")


def test_mcp_config_command_prints_hermes_config(capsys) -> None:
    exit_code = cli_main.main(
        ["mcp-config", "--client", "hermes", "--project", "/work/ai-crawler"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "mcp_servers:" in output
    assert "ai-crawler:" in output
    assert 'command: "uv"' in output


def test_mcp_config_command_prints_claude_code_config(capsys) -> None:
    exit_code = cli_main.main(
        ["mcp-config", "--client", "claude-code", "--project", "/work/ai-crawler"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"mcpServers"' in output
    assert '"ai-crawler"' in output


def test_mcp_config_command_prints_codex_config(capsys) -> None:
    exit_code = cli_main.main(
        ["mcp-config", "--client", "codex", "--project", "/work/ai-crawler"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '[mcp_servers."ai-crawler"]' in output
    assert 'command = "uv"' in output


def test_mcp_config_command_prints_npm_launcher_config(capsys) -> None:
    exit_code = cli_main.main(["mcp-config", "--client", "hermes", "--launcher", "npm"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert 'command: "npx"' in output
    assert '"-y"' in output
    assert '"@cafitac/ai-crawler"' in output
    assert '"mcp"' in output
    assert '"--project"' not in output
