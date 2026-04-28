# Open-source Generality Principles

This document records product and architecture lessons from the user's existing public agent-oriented OSS projects. The goal is to keep `ai-crawler` from becoming a one-off crawler for a single site and instead shape it as a reusable, composable open-source project.

Reference repositories inspected:

- `cafitac/agent-learner`
- `cafitac/hermit-agent`
- `cafitac/codex-channels`
- `cafitac/agent-memory` currently exists but is empty / has no HEAD at inspection time.

## Why this matters

`ai-crawler` should not be a hardcoded scraper, a site-specific reverse engineering script, or a browser automation wrapper. It should be a general system for:

1. discovering network behavior,
2. producing reusable crawler recipes,
3. validating those recipes,
4. running deterministic network-level crawls,
5. integrating with multiple agent / MCP / CLI environments.

The first real-world tests may involve a specific login-heavy website, but the architecture must remain site-agnostic.

## Patterns to carry over

### 1. Clear control-plane / execution-plane split

Observed pattern:

- `hermit-agent` separates premium planner/orchestrator from cheaper executor.
- `agent-learner` separates learning lifecycle from agent-specific adapters.
- `codex-channels` separates Codex-facing transport from generic interaction runtime.

Apply to `ai-crawler`:

- AI remains the control plane: planner, debugger, recipe author, repair loop.
- HTTP engine remains the data plane: deterministic request execution, retries, pagination, extraction.
- Browser probe remains discovery-only, not the primary crawler.

Non-goal:

- Do not let LLM calls enter the per-row/per-page crawl loop.

### 2. Core first, adapters second

Observed pattern:

- `agent-learner`: `core/` owns lifecycle/retrieval; `adapters/` owns runtime-specific integration.
- `codex-channels`: `core` owns interaction model; transports/backends are separate packages.
- `hermit-agent`: MCP, gateway, TUI, and tool surfaces wrap a shared agent core.

Apply to `ai-crawler`:

Core should own:

- request/response models,
- evidence bundle model,
- network trace normalization,
- endpoint inference,
- recipe schema,
- recipe validation,
- recipe runner,
- extraction runtime,
- safety/redaction policies.

Adapters should own:

- Playwright browser probe,
- Chrome DevTools Protocol capture,
- LLM provider integrations,
- MCP server surface,
- CLI commands,
- optional remote/proxy integrations.

Rule:

- MCP tools and CLI commands must be thin wrappers over core services.

### 3. Local-first default

Observed pattern:

- `codex-channels` defaults to local-first, single-machine operation.
- `agent-learner` stores project-local learning assets under project directories.
- `hermit-agent` defaults toward local / flat-rate executor routing where possible.

Apply to `ai-crawler`:

- Default operation should work locally.
- Default tests should not require internet, real LLM, real browser, or real proxy.
- Real browser, real LLM, and real-world crawling tests should be explicit opt-ins.
- Local fixture sites should be first-class.

### 4. Thin integration surfaces

Observed pattern:

- `codex-channels` treats Slack/Discord/Telegram as thin backends over a common interaction model.
- `agent-learner` treats Codex/Claude/Hermes as adapters over a common learning plane.
- `hermit-agent` exposes MCP/TUI/gateway paths while sharing the same underlying loop.

Apply to `ai-crawler`:

Integration surfaces:

- CLI,
- SDK,
- MCP server,
- optional hosted/service wrapper,
- optional agent-specific commands.

All should share:

- the same evidence model,
- the same recipe schema,
- the same validation logic,
- the same runner.

### 5. Doctor / bootstrap / smoke commands

Observed pattern:

- `agent-learner doctor`, `dashboard`, `bootstrap`, `rebuild-index`.
- `codex-channels doctor`, `plugin-bootstrap`, `demo`, `pending`, `inspect`, `reply`.
- `hermit install`, `hermit update`, `hermit-mcp-server`.

Apply to `ai-crawler`:

Recommended commands:

```bash
ai-crawler doctor
ai-crawler init
ai-crawler fixture serve
ai-crawler inspect-url URL
ai-crawler probe URL
ai-crawler generate-recipe URL --goal "..."
ai-crawler test-recipe recipe.yaml
ai-crawler run recipe.yaml --output out.jsonl
ai-crawler mcp
```

`doctor` should check:

- Python version,
- curl-cffi import,
- optional Playwright availability,
- optional browser install status,
- optional LLM provider configuration,
- MCP extra availability,
- writable cache/data directories,
- safety configuration.

### 6. Distribution should be boring and reliable

Observed pattern:

- Python package with `pyproject.toml`.
- npm wrapper where it improves install UX.
- release smoke checks and CI workflows.

Apply to `ai-crawler`:

Initial distribution path:

- Python package first.
- Optional extras:
  - `ai-crawler[browser]`
  - `ai-crawler[llm]`
  - `ai-crawler[mcp]`
  - `ai-crawler[dev]`
- Later npm wrapper only if it improves agent/MCP setup UX.

### 7. Human-readable artifacts

Observed pattern:

- `agent-learner` keeps file-native learning artifacts and human-readable indexes.
- `codex-channels` keeps inspectable state and protocol docs.
- `hermit-agent` documents task lifecycle and channel flow.

Apply to `ai-crawler`:

Artifacts should be inspectable:

- evidence bundles,
- redacted network traces,
- generated recipes,
- recipe test reports,
- repair logs,
- crawl run summaries.

Avoid opaque state that only the tool can understand.

### 8. Security and redaction are product features

Observed pattern:

- `codex-channels` explicitly treats payloads, tokens, callbacks, stale interaction IDs, and audit metadata as security concerns.
- `hermit-agent` has gateway/routing/security boundaries.

Apply to `ai-crawler`:

Must redact:

- cookies,
- authorization headers,
- CSRF tokens,
- API keys,
- session IDs,
- proxy credentials,
- form credentials,
- personally identifying account data where possible.

Must avoid:

- marketing as “undetectable scraping”,
- “bypass all protections”,
- unauthorized login circumvention,
- credential harvesting.

Positioning should remain:

- authorized crawling,
- internal QA/testing,
- owned or permitted data portability,
- research on allowed targets,
- reproducible network-level crawler generation.

### 9. First real-world test must not distort architecture

A login-heavy university portal or similar site can be a useful validation case for:

- multi-step session establishment,
- CSRF token capture,
- cookie jar replay,
- request dependency graph inference,
- authenticated API replay,
- recipe repair after drift.

But it must remain an adapter/fixture/test case, not a hardcoded product assumption.

Rules for such tests:

- Use only accounts and systems the user is authorized to access.
- Do not store credentials in repo, logs, recipes, or evidence bundles.
- Do not bypass CAPTCHA, MFA, access controls, or anti-abuse controls.
- Prefer a sanitized fixture that reproduces the same login/session mechanics.
- Treat real-site tests as opt-in and excluded from default CI.

## Design checklist added from these repos

Before adding a feature, ask:

1. Is this core logic or adapter logic?
2. Can the CLI, SDK, and MCP server all reuse it?
3. Does it work without a real LLM by using a mock or deterministic plan?
4. Does it work without a real browser unless browser probing is explicitly requested?
5. Does it produce a human-readable artifact?
6. Does it redact secrets by default?
7. Can it be tested against a local fixture site?
8. Does it make `ai-crawler` more general, or does it hardcode one website?

## Implication for MVP

The MVP should be shaped around reusable layers:

```text
ai_crawler.core
  models
  evidence
  traces
  inference
  recipe
  runner
  safety

ai_crawler.adapters
  browser_playwright
  llm
  mcp

ai_crawler.cli
  doctor
  inspect
  probe
  generate-recipe
  test-recipe
  run
```

The first implementation should prove the architecture on a local fixture before using any real login target.
