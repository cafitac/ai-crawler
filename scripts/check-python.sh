#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv run --extra dev ruff check .
uv run --extra dev mypy src
