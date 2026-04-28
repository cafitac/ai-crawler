# Development Sequence

## 목적

이 문서는 `ai-crawler`를 어떤 순서로 개발할지, 각 단계에서 무엇을 검증해야 다음 단계로 넘어갈 수 있는지 기록한다.

핵심 원칙:

- 먼저 deterministic core를 만든다.
- AI는 mock 가능한 interface부터 만든다.
- browser probe는 실제 크롤링 engine이 아니라 discovery 도구로 제한한다.
- MCP는 core가 안정된 뒤 얇은 wrapper로 붙인다.

---

## 전체 개발 순서

```text
0. Project bootstrap
1. Core data models
2. HTTP fetcher
3. Fixture test site
4. Browser network probe
5. Endpoint inference
6. Recipe model/loader
7. Recipe runner
8. CLI manual flow
9. AI AgentController loop
10. AI recipe generation/repair
11. MCP server
12. Production execution hardening
13. Advanced discovery
```

---

## Phase 0: Project Bootstrap

목표:

- Python package가 import되고 test/lint가 돌아가는 최소 프로젝트를 만든다.

작업:

- `pyproject.toml`
- `src/ai_crawler/__init__.py`
- `src/ai_crawler/cli.py`
- `tests/test_import.py`
- `ruff.toml`
- `pytest.ini`
- `.gitignore`

Exit criteria:

```bash
python -m ai_crawler.cli --help
pytest
ruff check .
```

모두 성공해야 한다.

주의:

- 아직 Playwright, MCP, LLM dependency를 기본 dependency에 넣지 않는다.
- optional extras로 분리할 준비를 한다.

---

## Phase 1: Core Data Models

목표:

- 모든 컴포넌트가 공유할 typed model을 먼저 만든다.

작업:

- `FetchResponse`
- `NetworkEvent`
- `EvidenceBundle`
- `AgentAction`
- `ToolResult`
- `Recipe`
- `CrawlResult`
- `FailureReport`

Exit criteria:

- Pydantic validation test 통과
- invalid input이 명확한 error를 낸다.
- JSON serialization/deserialization roundtrip이 된다.

주의:

- 모델에 provider-specific 타입을 넣지 않는다.
- LLM reasoning 전문을 저장하지 않는다. summary만 저장한다.

---

## Phase 2: HTTP Fetcher

목표:

- `curl-cffi` 기반 HTTP 요청을 안정적으로 실행한다.

작업:

- GET/POST 기본 지원
- headers/params/cookies/body
- timeout/retries/backoff
- impersonate option
- proxy option
- response normalization

Exit criteria:

- local fixture server 대상으로 GET/POST 테스트 통과
- retry test 통과
- timeout test 통과
- JSON/HTML response 모두 처리

주의:

- 처음부터 복잡한 proxy pool을 만들지 않는다.
- HTTP/3는 옵션만 남기고 MVP에서는 deep tuning하지 않는다.

---

## Phase 3: Fixture Test Site

목표:

- 외부 사이트에 의존하지 않는 end-to-end 테스트 환경을 만든다.

Fixture site 기능:

- `/products`: HTML page
- JS가 `/api/products?page=1` 호출
- page 1/2는 items 반환
- page 3은 empty items 반환
- `/api/products-cursor`: cursor pagination
- `/api/blocked`: 403/429 simulation
- `/api/schema-change`: field path 변경 simulation

Exit criteria:

- pytest에서 fixture server가 자동 실행된다.
- browser probe와 HTTP runner 모두 fixture server를 대상으로 테스트 가능하다.

주의:

- real public website 테스트는 opt-in integration test로만 둔다.

---

## Phase 4: Browser Network Probe

목표:

- Playwright/CDP로 페이지를 열고 XHR/fetch/document network events를 수집한다.

작업:

- page open
- request/response capture
- response body sample capture
- DOM title/text sample capture
- action support: wait, click, scroll
- HAR export/import optional

Exit criteria:

- fixture `/products`에서 `/api/products?page=1` 요청을 잡는다.
- button click으로 발생하는 request를 잡는다.
- probe timeout이 동작한다.

주의:

- browser dependency는 optional extra로 둔다.
- browser probe 결과는 evidence로만 쓰고, runner와 강결합하지 않는다.

---

## Phase 5: Endpoint Inference

목표:

- 수집된 network events에서 실제 데이터 API 후보를 고른다.

작업:

- candidate scoring
- JSON response detection
- repeated item array detection
- DOM visible text와 response field matching
- URL keyword signal
- GraphQL basic detection

Exit criteria:

- fixture에서 product API가 script/image/css보다 높은 점수를 받는다.
- score reason이 사람이 읽을 수 있게 나온다.

주의:

- AI 없이 rule-based detector가 먼저 동작해야 한다.
- AI는 detector 결과를 해석/선택하는 보조 역할로 시작한다.

---

## Phase 6: Recipe Model and Loader

목표:

- crawler recipe를 YAML로 저장/검증/로드한다.

작업:

- Pydantic recipe schema
- YAML loader/writer
- secret redaction
- schema version
- validation errors

Exit criteria:

- minimal recipe roundtrip 성공
- invalid recipe test 통과
- secret/cookie가 recipe에 직접 저장되지 않도록 guard

주의:

- recipe는 사람이 읽을 수 있어야 한다.
- AI가 생성한 recipe는 실행 전 반드시 validate한다.

---

## Phase 7: Recipe Runner

목표:

- 검증된 recipe를 실제 HTTP 요청으로 실행한다.

작업:

- request template rendering
- pagination loop
- JSONPath/CSS extraction
- item validation
- JSONL output
- stop condition
- limit support

Exit criteria:

- fixture API에서 page 1/2를 긁고 page 3 empty에서 멈춘다.
- output JSONL이 예상 item 수와 schema를 만족한다.

주의:

- 이 단계에서는 AI를 호출하지 않는다.
- runner는 deterministic해야 한다.

---

## Phase 8: Manual CLI Flow

목표:

- AI 없이도 수동 단계별 workflow가 가능해야 한다.

명령:

```bash
ai-crawler inspect URL
ai-crawler probe URL
ai-crawler generate-recipe URL --goal GOAL --out recipe.yaml
ai-crawler test-recipe recipe.yaml --limit 10
ai-crawler crawl recipe.yaml --output out.jsonl
```

Exit criteria:

- fixture site end-to-end 성공
- generated recipe가 사람이 읽을 수 있다.

주의:

- manual flow는 debugging과 테스트에 중요하다.
- auto mode가 실패해도 manual tool로 원인을 볼 수 있어야 한다.

---

## Phase 9: AgentController Loop

목표:

- AI가 action을 선택하고 engine이 실행하는 control loop를 만든다.

작업:

- `LLMClient` interface
- `MockLLMClient`
- `AgentState`
- allowed action schema
- `ToolRuntime`
- budget/max step guard

Exit criteria:

- MockLLMClient로 다음 sequence가 테스트된다.

```text
inspect_http -> probe_browser -> generate_recipe -> test_recipe -> run_crawler -> stop
```

주의:

- AI output은 반드시 structured action이어야 한다.
- 알 수 없는 action은 reject한다.
- budget 초과 시 안전하게 중단한다.

---

## Phase 10: Real LLM Integration

목표:

- OpenAI-compatible provider로 실제 AI action selection/generation을 지원한다.

작업:

- OpenAI-compatible client
- structured output schema
- prompt templates
- evidence compaction
- retry on invalid structured output

Exit criteria:

- opt-in integration test에서 실제 provider로 fixture recipe를 생성한다.
- 기본 test suite는 real LLM 없이 통과한다.

주의:

- API key가 없는 환경에서 test가 실패하면 안 된다.
- AI hallucination 방지를 위해 dry-run/validation은 필수다.

---

## Phase 11: MCP Server

목표:

- 외부 AI agent가 `ai-crawler`를 tool로 사용할 수 있게 한다.

작업:

- MCP stdio server
- optional streamable HTTP
- low-level tools
- high-level `auto_discover`, `auto_crawl`
- output sandbox

Exit criteria:

- MCP inspector 또는 Claude/Cursor/Hermes에서 tool list 확인
- fixture site 대상으로 `auto_crawl` 성공

주의:

- MCP handler 안에 business logic을 넣지 않는다.
- handler는 AgentController/ToolRuntime wrapper여야 한다.

---

## Phase 12: Production Execution Hardening

목표:

- 대량 실행 안정성을 높인다.

작업:

- async scheduler
- per-domain concurrency
- token bucket rate limit
- retry/backoff policy
- checkpoint/resume
- dedup
- proxy pool interface for legitimate routing/configuration only, not block evasion
- challenge detection boundary
- manual handoff/session import policy integration
- metrics

Exit criteria:

- fixture large crawl 시 interruption/resume 성공
- 10k item crawl simulation에서 memory leak 없음
- CAPTCHA/MFA/Cloudflare-like fixture challenge를 우회하지 않고 감지/중단/수동 handoff 상태로 분류
- raw cookie/token/session 값이 로그, recipe, evidence bundle에 평문 저장되지 않음

주의:

- 고속 크롤링 기본값은 보수적으로 둔다.
- 사용자가 명시적으로 concurrency를 올리게 한다.
- protection boundary는 bypass 대상이 아니라 challenge boundary로 취급한다.

---

## Phase 13: Advanced Discovery

목표:

- 현대 JS 앱과 복잡한 API를 더 잘 분석한다.

작업:

- Next.js/Nuxt embedded state extraction
- GraphQL operation detection
- JS bundle endpoint mining
- auth/token dependency graph
- cursor pagination inference
- schema-change repair

Exit criteria:

- real-world benchmark set에서 recipe generation 성공률 측정

주의:

- stealth/CAPTCHA bypass를 핵심 기능으로 홍보하지 않는다.
- authorized crawling/research/dev workflow에 초점을 둔다.
