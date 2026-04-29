"""Client-specific MCP configuration snippets."""

import json
from pathlib import Path

SUPPORTED_CLIENTS = ("hermes", "claude-code", "codex")
SUPPORTED_LAUNCHERS = ("uv", "npm")
NPM_PACKAGE = "@cafitac/ai-crawler"


def build_client_config(
    client: str,
    project_path: str | None = None,
    launcher: str = "uv",
) -> str:
    """Build a copy-pasteable MCP client config snippet."""
    normalized_client = client.strip().lower()
    if normalized_client not in SUPPORTED_CLIENTS:
        supported = ", ".join(SUPPORTED_CLIENTS)
        msg = f"Unsupported MCP client {client!r}; expected one of: {supported}"
        raise ValueError(msg)
    normalized_launcher = launcher.strip().lower()
    if normalized_launcher not in SUPPORTED_LAUNCHERS:
        supported = ", ".join(SUPPORTED_LAUNCHERS)
        msg = f"Unsupported MCP launcher {launcher!r}; expected one of: {supported}"
        raise ValueError(msg)
    command, args = _launcher_command(
        launcher=normalized_launcher,
        project_path=project_path,
    )
    if normalized_client == "hermes":
        return _hermes_yaml(command=command, args=args)
    if normalized_client == "claude-code":
        return _claude_json(command=command, args=args)
    return _codex_toml(command=command, args=args)


def _launcher_command(launcher: str, project_path: str | None) -> tuple[str, list[str]]:
    if launcher == "npm":
        return "npx", ["-y", NPM_PACKAGE, "mcp"]
    return "uv", _stdio_args(project_path=project_path)


def _stdio_args(project_path: str | None) -> list[str]:
    args = ["run"]
    if project_path:
        args.extend(["--project", str(Path(project_path))])
    args.extend([
        "--extra",
        "mcp",
        "--extra",
        "http",
        "ai-crawler",
        "mcp",
    ])
    return args


def _hermes_yaml(command: str, args: list[str]) -> str:
    args_yaml = ", ".join(json.dumps(arg) for arg in args)
    return (
        "mcp_servers:\n"
        "  ai-crawler:\n"
        f"    command: {json.dumps(command)}\n"
        f"    args: [{args_yaml}]\n"
        "    timeout: 300\n"
        "    connect_timeout: 60\n"
    )


def _claude_json(command: str, args: list[str]) -> str:
    return json.dumps(
        {"mcpServers": {"ai-crawler": {"command": command, "args": args}}},
        ensure_ascii=False,
        indent=2,
    )


def _codex_toml(command: str, args: list[str]) -> str:
    args_toml = ", ".join(json.dumps(arg) for arg in args)
    return (
        '[mcp_servers."ai-crawler"]\n'
        f'command = "{command}"\n'
        f"args = [{args_toml}]\n"
    )
