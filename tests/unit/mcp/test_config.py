"""MCP client configuration tests."""

import pytest

from ai_crawler.mcp.config import build_client_config


def test_build_hermes_mcp_config_uses_stdio_project_command() -> None:
    config = build_client_config(client="hermes", project_path="/work/ai-crawler")

    assert "mcp_servers:" in config
    assert "ai-crawler:" in config
    assert 'command: "uv"' in config
    assert '"--project"' in config
    assert '"/work/ai-crawler"' in config
    assert '"--extra", "mcp", "--extra", "http"' in config
    assert '"ai-crawler"' in config
    assert '"mcp"' in config


def test_build_claude_code_mcp_config_is_json_snippet() -> None:
    config = build_client_config(client="claude-code", project_path="/work/ai-crawler")

    assert '"mcpServers"' in config
    assert '"ai-crawler"' in config
    assert '"command": "uv"' in config
    assert '"mcp"' in config


def test_build_codex_mcp_config_is_toml_snippet() -> None:
    config = build_client_config(client="codex", project_path="/work/ai-crawler")

    assert '[mcp_servers."ai-crawler"]' in config
    assert 'command = "uv"' in config
    assert '"--project"' in config
    assert '"mcp"' in config


def test_build_hermes_mcp_config_supports_npm_launcher() -> None:
    config = build_client_config(client="hermes", launcher="npm")

    assert 'command: "npx"' in config
    assert '"-y"' in config
    assert '"@cafitac/ai-crawler"' in config
    assert '"mcp"' in config
    assert '"--project"' not in config


def test_build_client_config_rejects_unknown_launcher() -> None:
    with pytest.raises(ValueError, match="Unsupported MCP launcher"):
        build_client_config(client="hermes", launcher="pipx")
