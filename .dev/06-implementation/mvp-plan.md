# MVP Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

## Goal

Build the first working `ai-crawler` MVP: given a URL and goal, capture network traffic with a browser probe, identify a likely JSON API, generate a recipe, test it with `curl-cffi`, and run it to produce JSONL.

## Architecture

The MVP has four layers: probe, inference, recipe, execution. AI integration starts with a mockable LLM client interface so tests do not depend on real LLM calls. MCP is added after the core CLI works.

## Tech Stack

- Python 3.11+
- `curl-cffi` for HTTP fetching
- `playwright` for browser probe
- `pydantic` for models
- `typer` or `click` for CLI
- `pytest` for tests
- `jsonpath-ng` or small internal JSONPath subset
- `mcp` for MCP server later

---

## Phase 0: Project bootstrap

### Task 0.1: Create Python package skeleton

Files:

- Create: `pyproject.toml`
- Create: `src/ai_crawler/__init__.py`
- Create: `src/ai_crawler/cli.py`
- Create: `tests/test_import.py`

Acceptance:

- `python -m ai_crawler.cli --help` works
- `pytest` passes

### Task 0.2: Add development tooling

Files:

- Create: `ruff.toml`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `README.md`

Acceptance:

- `ruff check .` works
- `pytest` works

---

## Phase 1: HTTP fetcher

### Task 1.1: Define fetcher response model

Files:

- Create: `src/ai_crawler/fetchers/types.py`
- Test: `tests/unit/test_fetcher_types.py`

Model:

```python
class FetchResponse(BaseModel):
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    text: str | None = None
    content_type: str | None = None
```

Acceptance:

- Model can represent JSON and HTML responses.

### Task 1.2: Implement curl-cffi fetcher

Files:

- Create: `src/ai_crawler/fetchers/curl_cffi_fetcher.py`
- Test: `tests/unit/test_curl_cffi_fetcher.py`

Features:

- GET request
- headers
- params
- cookies
- timeout
- retries
- impersonate option

Acceptance:

- Can fetch a local test HTTP server.
- Retry behavior is tested with failing endpoint.

---

## Phase 2: Browser probe

### Task 2.1: Define network event model

Files:

- Create: `src/ai_crawler/probe/models.py`
- Test: `tests/unit/test_probe_models.py`

Model fields:

- id
- url
- method
- resource_type
- request_headers
- request_body
- status
- response_headers
- response_body_sample
- content_type
- timing

### Task 2.2: Implement Playwright network capture

Files:

- Create: `src/ai_crawler/probe/browser_probe.py`
- Test: `tests/integration/test_browser_probe.py`

Features:

- Open URL
- Capture requests/responses
- Store XHR/fetch/document responses
- Return DOM title and visible text sample

Acceptance:

- Against a local HTML page that calls `/api/products`, probe captures the API request.

### Task 2.3: Add optional actions

Files:

- Modify: `src/ai_crawler/probe/browser_probe.py`
- Test: `tests/integration/test_browser_probe_actions.py`

Actions:

- wait
- click selector
- scroll N times

Acceptance:

- Probe can trigger a local page button that fetches API data.

---

## Phase 3: Endpoint inference

### Task 3.1: Implement endpoint candidate scoring

Files:

- Create: `src/ai_crawler/inference/endpoint_detector.py`
- Test: `tests/unit/test_endpoint_detector.py`

Scoring signals:

- JSON content type
- repeated objects/arrays
- URL contains api/search/graphql/products
- response contains visible DOM text
- resource_type is xhr/fetch

Acceptance:

- Product API ranks above images/scripts/styles.

### Task 3.2: Implement simple schema inference

Files:

- Create: `src/ai_crawler/inference/schema_inference.py`
- Test: `tests/unit/test_schema_inference.py`

Features:

- detect items array path
- infer field names and primitive types

Acceptance:

- Finds `$.items` from `{"items": [{"name": "A", "price": 1}]}`.

### Task 3.3: Implement pagination detection MVP

Files:

- Create: `src/ai_crawler/inference/pagination_detector.py`
- Test: `tests/unit/test_pagination_detector.py`

MVP support:

- page number param
- offset/limit param
- cursor field in response

Acceptance:

- Detects `page=1` in candidate URL.

---

## Phase 4: Recipe system

### Task 4.1: Define recipe Pydantic models

Files:

- Create: `src/ai_crawler/recipes/models.py`
- Test: `tests/unit/test_recipe_models.py`

Acceptance:

- Minimal recipe validates.
- Invalid recipe produces clear error.

### Task 4.2: Implement YAML loader/writer

Files:

- Create: `src/ai_crawler/recipes/loader.py`
- Test: `tests/unit/test_recipe_loader.py`

Acceptance:

- Recipe roundtrip load/write works.

### Task 4.3: Generate deterministic recipe from candidate

Files:

- Create: `src/ai_crawler/inference/recipe_generator.py`
- Test: `tests/unit/test_recipe_generator.py`

Note:

- This task does not require LLM yet.
- Rule-based generation is enough for MVP.

Acceptance:

- Candidate `/api/products?page=1` produces a valid recipe.

---

## Phase 5: Execution engine

### Task 5.1: Implement recipe runner for one request

Files:

- Create: `src/ai_crawler/execution/runner.py`
- Test: `tests/unit/test_runner_single_request.py`

Acceptance:

- Runs recipe against local JSON API and extracts items.

### Task 5.2: Add pagination loop

Files:

- Modify: `src/ai_crawler/execution/runner.py`
- Test: `tests/unit/test_runner_pagination.py`

Acceptance:

- Fetches page 1..N until empty items.

### Task 5.3: Add JSONL output

Files:

- Create: `src/ai_crawler/output/jsonl.py`
- Test: `tests/unit/test_jsonl_output.py`

Acceptance:

- Items are written as newline-delimited JSON.

---

## Phase 6: CLI

### Task 6.1: Add `inspect` command

Command:

```bash
ai-crawler inspect https://example.com/products --goal "상품명 가격"
```

Acceptance:

- Prints site summary and endpoint candidates.

### Task 6.2: Add `generate-recipe` command

Command:

```bash
ai-crawler generate-recipe https://example.com/products --goal "상품명 가격" --out recipes/products.yaml
```

Acceptance:

- Creates valid recipe file.

### Task 6.3: Add `test-recipe` command

Command:

```bash
ai-crawler test-recipe recipes/products.yaml --limit 10
```

Acceptance:

- Prints item count and sample items.

### Task 6.4: Add `crawl` command

Command:

```bash
ai-crawler crawl recipes/products.yaml --limit 1000 --output outputs/products.jsonl
```

Acceptance:

- Writes JSONL output.

---

## Phase 7: AI integration

### Task 7.1: Define LLM client interface

Files:

- Create: `src/ai_crawler/ai/client.py`
- Test: `tests/unit/test_llm_client.py`

Acceptance:

- `MockLLMClient` can return structured recipe patch.

### Task 7.2: Add OpenAI-compatible client

Files:

- Modify: `src/ai_crawler/ai/client.py`
- Test: `tests/unit/test_openai_compatible_client.py`

Acceptance:

- Unit tests mock HTTP call; no real API call.

### Task 7.3: Add AI repair interface

Files:

- Create: `src/ai_crawler/ai/orchestrator.py`
- Test: `tests/unit/test_ai_repair.py`

Acceptance:

- Given failure report, AI can return recipe patch through mock client.

---

## Phase 8: MCP server

### Task 8.1: Add MCP server skeleton

Files:

- Create: `src/ai_crawler/mcp/server.py`
- Test: `tests/unit/test_mcp_server_tools.py`

Tools:

- inspect_site
- discover_network_api
- generate_recipe
- test_recipe
- run_crawler
- repair_recipe
- explain_failure

### Task 8.2: Wire CLI command `mcp`

Command:

```bash
ai-crawler mcp
```

Acceptance:

- MCP server starts with stdio transport.

---

## Verification for MVP

Create a local fixture site:

- HTML page `/products`
- JS fetches `/api/products?page=1`
- API returns JSON products
- page 3 returns empty items

End-to-end command:

```bash
ai-crawler generate-recipe http://localhost:8000/products --goal "상품명 가격" --out /tmp/products.yaml
ai-crawler test-recipe /tmp/products.yaml --limit 5
ai-crawler crawl /tmp/products.yaml --output /tmp/products.jsonl
```

Expected:

- recipe file exists
- test returns sample items
- output JSONL contains products

---

## Not in MVP

- distributed crawling
- browser stealth bypass
- CAPTCHA solving
- login automation
- complex GraphQL mutation/session flows
- proxy scoring
- dashboard
- cloud deployment

These are later phases.
