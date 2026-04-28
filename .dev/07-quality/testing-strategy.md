# Testing Strategy

## 목표

`ai-crawler`는 AI, 브라우저, 네트워크, 외부 사이트가 얽히는 프로젝트다.
따라서 테스트는 외부 의존성을 최대한 분리하고, deterministic한 core부터 검증해야 한다.

기본 원칙:

- 기본 test suite는 인터넷, real browser, real LLM, real proxy에 의존하지 않는다.
- 외부 의존 테스트는 opt-in으로 분리한다.
- AI output은 반드시 schema validation과 dry-run으로 검증한다.
- browser probe는 fixture site에서 재현 가능해야 한다.

---

## 테스트 계층

```text
Unit tests
  -> model, parser, inference, recipe validation

Component tests
  -> fetcher, runner, endpoint detector

Integration tests
  -> local fixture site + browser probe + recipe runner

AI integration tests
  -> MockLLM by default, real LLM opt-in

MCP tests
  -> tool registration, tool call contract, smoke test

End-to-end tests
  -> fixture site full workflow

Optional real-world tests
  -> selected public sites, manually/CI opt-in only
```

---

## 1. Unit Tests

대상:

- Pydantic models
- recipe schema
- endpoint scoring
- pagination detection
- schema inference
- JSONPath/CSS extraction helpers
- action schema validation

특징:

- 빠름
- 외부 네트워크 없음
- browser 없음
- LLM 없음

예상 명령:

```bash
pytest tests/unit -q
```

Exit criteria:

- PR마다 반드시 통과
- flaky test 없어야 함

---

## 2. Component Tests

대상:

- curl-cffi fetcher
- recipe runner
- output writer
- rate limiter
- retry/backoff

테스트 방식:

- local HTTP test server 사용
- 실패/timeout/status code를 controlled하게 simulation

예상 fixture server endpoints:

```text
/html/products
/api/products?page=1
/api/products?page=2
/api/products?page=3
/api/slow
/api/flaky
/api/blocked
/api/schema-change
```

명령:

```bash
pytest tests/component -q
```

---

## 3. Browser Probe Integration Tests

대상:

- Playwright browser probe
- network event capture
- scroll/click action
- response body sample capture

조건:

- `ai-crawler[browser]` extra 설치 필요
- CI에서는 browser test job을 별도 분리

명령:

```bash
pytest tests/integration/browser -q
```

Skip 조건:

- Playwright 미설치
- 브라우저 binary 없음
- `AI_CRAWLER_SKIP_BROWSER_TESTS=1`

Exit criteria:

- fixture page의 XHR/fetch request를 정확히 캡처한다.
- timeout 내에 종료한다.
- browser process가 남지 않는다.

---

## 4. AI Tests

### 기본: MockLLMClient

기본 test suite에서는 실제 LLM API를 호출하지 않는다.

Mock scenario:

```text
inspect_http -> probe_browser -> generate_recipe -> test_recipe -> run_crawler
```

검증:

- AgentController가 AI action을 순서대로 실행
- invalid action reject
- budget exceeded 처리
- malformed structured output retry/stop

명령:

```bash
pytest tests/unit/test_agent_controller.py -q
```

### Optional: Real LLM Integration

실제 LLM 테스트는 opt-in.

환경 변수:

```bash
AI_CRAWLER_RUN_LLM_TESTS=1
AI_CRAWLER_LLM_PROVIDER=openai-compatible
AI_CRAWLER_LLM_BASE_URL=...
AI_CRAWLER_LLM_API_KEY=...
AI_CRAWLER_LLM_MODEL=...
```

명령:

```bash
AI_CRAWLER_RUN_LLM_TESTS=1 pytest tests/integration/llm -q
```

주의:

- CI 기본 job에서는 실행하지 않는다.
- snapshot에 API key나 raw page content를 저장하지 않는다.
- real LLM 테스트는 pass/fail이 flaky할 수 있으므로 smoke 중심으로 둔다.

---

## 5. MCP Tests

대상:

- MCP server starts
- tool registration
- tool schemas
- tool call smoke test

명령:

```bash
pytest tests/integration/mcp -q
```

검증 tool:

- `inspect_site`
- `discover_network_api`
- `generate_recipe`
- `test_recipe`
- `run_crawler`
- `repair_recipe`
- `auto_crawl`

주의:

- MCP handler는 internal API wrapper여야 한다.
- business logic은 별도 unit/component test에서 검증한다.

---

## 6. End-to-End Fixture Test

MVP의 가장 중요한 테스트다.

시나리오:

```text
1. fixture site 실행
2. ai-crawler auto /products --goal "상품명 가격"
3. AgentController가 mock AI loop 실행
4. browser probe가 /api/products?page=1 캡처
5. recipe 생성
6. recipe test 성공
7. crawl 실행
8. products.jsonl 생성
```

명령:

```bash
pytest tests/e2e/test_fixture_auto_crawl.py -q
```

성공 기준:

- JSONL 파일 생성
- item count == expected
- field schema match
- browser는 discovery 중에만 사용
- crawl execution 단계에서는 browser 사용 없음

---

## 7. Optional Real-World Tests

목적:

- 실제 사이트에서 discovery 품질을 측정한다.

주의:

- 기본 CI에서 실행하지 않는다.
- robots.txt/ToS를 확인한다.
- 낮은 rate로 실행한다.
- 대상 사이트 목록은 별도 allowlist로 관리한다.

명령:

```bash
AI_CRAWLER_RUN_REALWORLD_TESTS=1 pytest tests/realworld -q
```

수집 metric:

- API discovery success rate
- recipe generation success rate
- first test pass rate
- repair success rate
- average browser probe time
- HTTP crawl throughput

---

## Test Data and Snapshots

저장 가능한 것:

- fixture response
- synthetic HAR
- sanitized network events
- sanitized recipe
- anonymized failure report

저장하면 안 되는 것:

- real cookies
- auth tokens
- API keys
- personal data
- raw private page content

---

## CI Matrix 제안

### Job 1: unit

```bash
pip install -e .[dev]
pytest tests/unit -q
ruff check .
```

### Job 2: component

```bash
pip install -e .[dev]
pytest tests/component -q
```

### Job 3: browser integration

```bash
pip install -e .[dev,browser]
playwright install chromium
pytest tests/integration/browser -q
```

### Job 4: mcp integration

```bash
pip install -e .[dev,mcp]
pytest tests/integration/mcp -q
```

### Manual/optional: llm

```bash
AI_CRAWLER_RUN_LLM_TESTS=1 pytest tests/integration/llm -q
```

---

## Coverage Expectations

MVP target:

- unit/core: 90%+
- execution runner: 85%+
- AI orchestration with mock: 85%+
- browser probe: behavior coverage over line coverage
- real LLM: smoke only

---

## Flaky Test Policy

Flaky tests are not acceptable in default CI.

If a test is flaky because it uses browser/network/LLM:

1. Move it to opt-in integration suite.
2. Add timeout and deterministic fixture.
3. Record failure reason.
4. Do not hide with broad retry unless testing retry itself.

---

## Minimum Test Before Release

Before tagging a release:

```bash
ruff check .
pytest tests/unit tests/component tests/e2e -q
pytest tests/integration/browser -q
pytest tests/integration/mcp -q
```

Optional but recommended:

```bash
AI_CRAWLER_RUN_LLM_TESTS=1 pytest tests/integration/llm -q
AI_CRAWLER_RUN_REALWORLD_TESTS=1 pytest tests/realworld -q
```
