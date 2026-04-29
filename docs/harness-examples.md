# ai-crawler harness examples

This page collects copy-paste examples for the three main harness-facing surfaces:

- published npm wrapper
- stdio MCP server
- embedded Python SDK

## 1. Published wrapper quick checks

Run these from outside the repo to confirm the published package is usable:

```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
npm exec --yes --package @cafitac/ai-crawler@0.1.2 ai-crawler -- --version
npm exec --yes --package @cafitac/ai-crawler@0.1.2 ai-crawler -- doctor
npm exec --yes --package @cafitac/ai-crawler@0.1.2 ai-crawler -- mcp-config --client hermes --launcher npm
```

Expected shape:

```yaml
mcp_servers:
  ai-crawler:
    command: "npx"
    args: ["-y", "@cafitac/ai-crawler", "mcp"]
    timeout: 300
    connect_timeout: 60
```

## 2. MCP client snippets

Local repo / uv-project snippet for Hermes:

```bash
uv run ai-crawler mcp-config --client hermes --project /path/to/ai-crawler
```

Published npm-first snippet for Hermes:

```bash
uv run ai-crawler mcp-config --client hermes --launcher npm
```

Codex TOML snippet:

```bash
uv run ai-crawler mcp-config --client codex --launcher npm
```

Claude Code JSON snippet:

```bash
uv run ai-crawler mcp-config --client claude-code --launcher npm
```

Run the server directly:

```bash
uv run --extra mcp --extra http ai-crawler mcp
```

Or through the published wrapper:

```bash
npm exec --yes --package @cafitac/ai-crawler@0.1.2 ai-crawler -- mcp
```

## 3. Python SDK compile_url flow

Minimal end-to-end example:

```python
from ai_crawler import AICrawler

crawler = AICrawler()
result = crawler.compile_url(
    "https://example.com/products",
    goal="collect products",
    evidence_path="evidence.json",
    recipe_path="recipe.yaml",
    repaired_recipe_path="repaired.recipe.yaml",
    initial_output_path="test.jsonl",
    final_output_path="crawl.jsonl",
    report_path="auto.report.json",
)

print(result.ok)
print(result.exit_code)
print(result.report["command_type"])
print(result.report["phase_diagnostics"])
```

If you already have evidence, use `auto(...)` instead:

```python
from ai_crawler import AICrawler

crawler = AICrawler()
result = crawler.auto("evidence.json")
print(result.report["summary"])
```

For tests or embedding, inject a fake fetcher and fake probe:

```python
crawler = AICrawler(fetcher=my_fake_fetcher, probe=my_fake_probe)
```

## 4. CLI compile flow

One-command compile from a URL:

```bash
uv run --extra browser --extra http ai-crawler compile \
  https://example.com/products \
  --goal "collect products" \
  --evidence evidence.json \
  --recipe recipe.yaml \
  --repaired-recipe repaired.recipe.yaml \
  --initial-output test.jsonl \
  --final-output crawl.jsonl \
  --report auto.report.json
```

If the browser extras are not installed yet:

```bash
uv sync --extra browser --extra http --extra mcp --extra dev
```

## 5. Recommended validation bundle after changes

For harness-facing changes, the standard validation bundle is:

```bash
bash scripts/check-python.sh
bash scripts/verify-ai-harness.sh
uv run --extra http python scripts/smoke-mcp-auto-compile.py
```

For release validation, also follow `docs/release-runbook.md`.
