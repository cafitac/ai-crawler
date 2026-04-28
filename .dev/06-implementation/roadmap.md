# Roadmap

## Product Direction

`ai-crawler` should become a network-first crawler generator.

The product should not compete head-on with Playwright wrappers or scraping MCP servers.
Instead, it should own this niche:

> Use AI to discover the real network/API layer of a website, compile it into a reusable crawler recipe, then run that recipe at high speed without a browser.

---

## Milestone 1: Local MVP

Goal:

- One developer can run CLI locally and generate a working HTTP recipe from a JS-rendered page.

Features:

- Python project scaffold
- curl-cffi fetcher
- Playwright browser probe
- network event capture
- endpoint candidate scoring
- simple recipe generation
- recipe runner
- JSONL output
- CLI commands

Success criteria:

- Local fixture site works end-to-end.
- One real public demo site works without login.
- Browser is used only during discovery, not during run.

---

## Milestone 2: AI-assisted recipe generation

Goal:

- LLM can help choose endpoint, infer schema, and generate/repair recipe.

Features:

- LLM client abstraction
- OpenAI-compatible adapter
- Anthropic adapter optional
- evidence bundle builder
- structured output parser
- recipe repair loop
- failure classification

Success criteria:

- Given network capture from a real site, AI creates a usable recipe.
- Given broken items path, AI repairs it.
- Tests use MockLLMClient; no tests require paid API.

---

## Milestone 3: MCP server

Goal:

- Agent can use ai-crawler as a tool server.

Features:

- MCP stdio server
- optional streamable HTTP server
- tools:
  - inspect_site
  - discover_network_api
  - generate_recipe
  - test_recipe
  - run_crawler
  - repair_recipe
  - explain_failure

Success criteria:

- Claude/Cursor/Hermes can connect.
- Agent can create recipe and run it with natural language.
- Tool descriptions encourage network-first behavior.

---

## Milestone 4: Production-grade HTTP execution

Goal:

- Fast and reliable high-volume crawling.

Features:

- async scheduler
- per-domain concurrency
- token bucket rate limiter
- retry/backoff
- ban detection
- proxy pool interface
- cookie jar isolation
- checkpoint/resume
- dedup
- streaming output

Success criteria:

- 10k+ URL crawl from recipe without browser.
- Can resume after interruption.
- Can throttle per domain.

---

## Milestone 5: Advanced discovery

Goal:

- Better API discovery beyond simple XHR.

Features:

- HAR import/export
- GraphQL operation detection
- Next.js/Nuxt/SvelteKit embedded data extraction
- script bundle endpoint mining
- pagination strategy inference
- auth/token dependency graph
- localStorage/sessionStorage modeling

Success criteria:

- Detects APIs from modern JS apps.
- Can infer cursor pagination.
- Can refresh CSRF/token from HTML or bootstrap JSON.

---

## Milestone 6: Scale and operations

Goal:

- Production operation features.

Features:

- job management
- crawl metrics
- failure dashboard
- proxy health scoring
- output sinks: S3, Postgres, Kafka, webhook
- distributed queue optional

Success criteria:

- Long-running crawl jobs are observable.
- Failures are categorized and repairable.

---

## Milestone 7: Hosted/Team version optional

Goal:

- If this becomes a product, provide team workflows.

Features:

- recipe registry
- versioned recipes
- scheduled recrawls
- team secrets
- browser probe workers
- managed proxy integration
- audit logs

---

## Design constraints

- Do not make browser the default execution path.
- Do not call AI inside tight crawl loops.
- Do not store secrets in recipe files.
- Do not silently crawl outside allowed domains.
- Do not hide failures; produce failure reports.
