#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv run --extra dev pytest \
  tests/unit/core/security/test_redaction.py \
  tests/unit/core/diagnostics/test_failure_classification.py \
  tests/unit/core/agent/test_recipe_testing.py \
  tests/unit/core/agent/test_auto_compiler.py \
  tests/unit/cli/test_test_recipe_command.py \
  tests/unit/cli/test_auto_command.py \
  tests/unit/cli/test_mcp_config_command.py \
  tests/unit/sdk/test_client.py \
  tests/unit/mcp/test_config.py \
  tests/unit/mcp/test_tools.py \
  tests/test_cli.py \
  -q
uv run --extra dev pytest tests -q
uv run --extra dev ruff check .
uv run python -m ai_crawler.cli --help
uv run ai-crawler doctor
