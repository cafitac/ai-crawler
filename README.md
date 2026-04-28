# ai-crawler

AI-driven network-first crawler compiler for authorized workflows.

`ai-crawler` turns captured network evidence into reusable crawler recipes. The browser is used as a short-lived probe for API discovery, not as the crawling engine. Bulk collection runs through deterministic HTTP replay with `curl-cffi`.

```text
Browser is not the crawler. Browser is the probe.
AI is not the request loop. AI is the planner/debugger/recipe author.
```

## What it is

`ai-crawler` is an early-stage Python OSS library and CLI for building crawler recipes from network evidence.

It focuses on:

- Network-first API discovery and replay
- Recipe generation, testing, repair, and deterministic execution
- Simple CLI defaults for humans and AI harnesses
- Python SDK facade for application integrations
- stdio MCP server for Hermes, Claude Code, Codex, and other agents
- Local-first tests with fake transports and fixture sites
- Security boundaries: redaction, challenge detection, and no CAPTCHA/MFA/bot-challenge bypass logic

## Install for local development

```bash
git clone https://github.com/cafitac/ai-crawler.git
cd ai-crawler
uv sync --extra dev --extra http --extra mcp
```

If you are already inside a local checkout:

```bash
uv sync --extra dev --extra http --extra mcp
```

## Quick start

The main AI-harness command is:

```bash
ai-crawler auto evidence.json --json
```

With a local checkout:

```bash
uv run --extra http ai-crawler auto evidence.json --json
```

This writes default artifacts:

```text
recipe.yaml              # initial generated recipe
repaired.recipe.yaml     # repaired/final recipe
test.jsonl               # initial diagnostic crawl output
crawl.jsonl              # final crawl output
auto.report.json         # stable machine-readable report
```

The JSON report includes:

- final success/failure status
- recipe/output paths
- initial and final crawl results
- bounded/redacted diagnostic samples
- failure classifications such as `success`, `extraction_failed`, `http_error`, `no_response`, and `challenge_detected`

## Evidence format

Minimal evidence JSON:

```json
{
  "target_url": "https://example.com/products",
  "goal": "collect products",
  "events": [
    {
      "method": "GET",
      "url": "https://example.com/api/products?page=1",
      "status_code": 200,
      "resource_type": "fetch"
    }
  ]
}
```

Generate and run manually:

```bash
uv run --extra http ai-crawler generate-recipe evidence.json
uv run --extra http ai-crawler test-recipe recipe.yaml
uv run --extra http ai-crawler repair-recipe recipe.yaml
uv run --extra http ai-crawler test-recipe repaired.recipe.yaml --output crawl.jsonl
```

## MCP usage

Generate client config snippets:

```bash
uv run ai-crawler mcp-config --client hermes --project /path/to/ai-crawler
uv run ai-crawler mcp-config --client claude-code --project /path/to/ai-crawler
uv run ai-crawler mcp-config --client codex --project /path/to/ai-crawler
```

Run as a stdio MCP server:

```bash
uv run --extra mcp --extra http ai-crawler mcp
```

Exposed tools:

- `auto_compile`
- `generate_recipe`
- `test_recipe`
- `repair_recipe`

Hermes development snippet shape:

```yaml
mcp_servers:
  ai-crawler:
    command: "uv"
    args: ["run", "--project", "/path/to/ai-crawler", "--extra", "mcp", "--extra", "http", "ai-crawler", "mcp"]
    timeout: 300
    connect_timeout: 60
```

## Python SDK

```python
from ai_crawler import AICrawler

crawler = AICrawler()
result = crawler.auto("evidence.json")
print(result.ok)
print(result.exit_code)
print(result.report)
```

For tests or embedded usage, inject a fake fetcher:

```python
crawler = AICrawler(fetcher=my_fake_fetcher)
```

## Verification

Full project verification:

```bash
bash scripts/verify-ai-harness.sh
```

MCP `auto_compile` fixture smoke test:

```bash
uv run --extra http python scripts/smoke-mcp-auto-compile.py
```

This starts a local fixture HTTP site and verifies `generate -> test -> repair -> retest` without external internet, a real browser, or a real LLM.

## Security and compliance boundary

`ai-crawler` is intended for authorized crawling, internal QA/testing, research, owned or allowed web property monitoring, and data portability workflows.

It does not implement:

- CAPTCHA solving
- MFA bypass
- Cloudflare/bot-challenge bypass
- stealth fingerprint manipulation
- evasion proxy rotation

Challenge-like responses are classified and surfaced as requiring human/manual handoff where appropriate.

Sensitive values in diagnostic reports are redacted, including common bearer tokens, cookies, session IDs, API keys, and JSON-embedded token fields.

## Documentation

Development docs live under `.dev/`:

- `.dev/README.md`
- `.dev/03-ai/auto-harness-contract.md`
- `.dev/04-mcp/server.md`
- `.dev/08-operations/security-and-compliance.md`
- `.dev/08-operations/challenge-handling-policy.md`

## Status

Alpha. The deterministic recipe compiler, CLI, SDK facade, MCP server, redaction, failure classification, and fixture smoke tests are implemented. Real browser probe and real LLM provider integrations are intentionally optional/future layers behind adapter boundaries.

## License

MIT
