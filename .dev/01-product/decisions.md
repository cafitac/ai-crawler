# Development Decisions

## Decision 1: Project name

Use `ai-crawler`.

Reason:

- Short and clear
- Describes the broader product better than `network-first-crawler`
- `network-first` remains the technical philosophy, not necessarily the package name

Package name candidate:

- Python import: `ai_crawler`
- CLI command: `ai-crawler`
- Repository directory: `ai-crawler`

---

## Decision 2: Network-first, browser-probe architecture

The browser is not the crawler.
The browser is used to inspect and learn.

Execution priority:

1. HTTP/curl-cffi
2. HTTP with refreshed state/cookies
3. Browser probe for discovery/repair
4. Browser fallback only when unavoidable

---

## Decision 3: AI is control-plane only

AI should not sit inside the per-request crawl loop.

AI responsibilities:

- interpret evidence
- select endpoint
- generate recipe
- repair recipe
- explain failures

Engine responsibilities:

- request scheduling
- rate limiting
- retries
- parsing
- output

---

## Decision 4: Recipe-first design

Every discovered crawler should become a recipe.

Benefits:

- reproducible
- reviewable
- testable
- repairable
- reusable without AI

---

## Decision 5: MCP is a first-class interface, not the core

MCP server should wrap the same internal APIs used by CLI and Python SDK.

Do not put business logic inside MCP tool handlers.

---

## Decision 6: Tests should not require paid LLM calls

Use `MockLLMClient` for tests.
Integration tests with real LLM provider should be opt-in.

---

## Decision 7: Browser dependencies should be optional

Base install should support HTTP execution.
Browser probe should be an extra.

Possible extras:

```bash
pip install "ai-crawler[browser]"
pip install "ai-crawler[ai]"
pip install "ai-crawler[mcp]"
pip install "ai-crawler[all]"
```
