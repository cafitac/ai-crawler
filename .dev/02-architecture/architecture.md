# ai-crawler Architecture

## 목표

브라우저 자동화 기반 스크래퍼가 아니라, 네트워크 요청을 추론하고 재생하는 AI 기반 크롤러를 만든다.

핵심 목표:

- 브라우저 사용 최소화
- HTTP/TLS/network-level crawling 최적화
- AI 기반 API discovery
- AI 기반 crawler recipe 생성/수정
- MCP/CLI/Python SDK 모두 지원
- 대량 크롤링에 적합한 실행 엔진 제공

---

## 전체 구조

```text
User / AI Agent
    |
    | CLI / Python SDK / MCP
    v
Control Plane
    |
    +-- AI Orchestrator
    |     +-- LLM Provider Adapter
    |     +-- Tool Router
    |     +-- Reasoning Trace Store
    |
    +-- Discovery Engine
    |     +-- Browser Probe
    |     +-- Network Capture
    |     +-- DOM Snapshot Capture
    |     +-- Storage/Cookie Capture
    |
    +-- Inference Engine
    |     +-- Endpoint Candidate Detector
    |     +-- Pagination Detector
    |     +-- Token/Cookie Dependency Detector
    |     +-- Schema Inference
    |     +-- Recipe Generator
    |
    +-- Execution Engine
    |     +-- curl-cffi Fetcher
    |     +-- Async Scheduler
    |     +-- Proxy Pool
    |     +-- Rate Limiter
    |     +-- Retry/Backoff
    |     +-- Ban Detection
    |
    +-- Validation Engine
    |     +-- Recipe Test Runner
    |     +-- Data Schema Validator
    |     +-- Failure Classifier
    |     +-- Repair Loop
    |
    v
Output
    +-- JSONL / CSV / Parquet
    +-- Streaming items
    +-- Webhook
    +-- MCP structured result
```

---

## 주요 컴포넌트

### 1. Browser Probe

브라우저는 실제 크롤링용이 아니라 관찰용이다.

역할:

- Playwright 또는 Chrome DevTools Protocol로 페이지 열기
- network request/response 캡처
- XHR/fetch/GraphQL endpoint 수집
- request headers, cookies, localStorage, sessionStorage 수집
- DOM snapshot 저장
- user interaction 시나리오 실행
- infinite scroll/pagination trigger 관찰

MVP에서는 Playwright를 사용한다.

나중에 CDP 직접 연결을 추가할 수 있다.

### 2. Network Capture

수집 대상:

- URL
- method
- request headers
- request body
- response status
- response headers
- response body sample
- resource type: document, xhr, fetch, script, image 등
- initiator 정보
- timing
- redirect chain
- cookies set/read

저장 포맷:

- 내부 JSON event log
- 선택적으로 HAR export/import 지원

### 3. Endpoint Candidate Detector

많은 네트워크 요청 중 실제 데이터 API 후보를 찾는다.

우선순위 신호:

- response content-type이 JSON
- 응답 안에 반복 item 배열 존재
- DOM에 렌더링된 텍스트와 API 응답 필드가 매칭됨
- URL에 `api`, `graphql`, `search`, `product`, `listing`, `page`, `cursor` 등이 포함됨
- response size가 충분히 큼
- image/css/font/script 제외
- 사용자의 goal과 필드명이 유사함

### 4. Recipe Generator

AI와 rule engine이 함께 crawler recipe를 만든다.

생성 대상:

- entry URL
- API URL
- method
- headers
- cookie policy
- auth/token extraction
- pagination strategy
- item path
- field extraction schema
- retry/backoff policy
- ban detection signal
- fallback policy

### 5. Execution Engine

실제 크롤링은 가능한 한 브라우저 없이 수행한다.

MVP fetcher:

- `curl-cffi`
- async 지원
- browser TLS impersonation
- proxy 지원
- retry/backoff
- per-domain concurrency
- response parser

추후:

- `httpx` backend 옵션
- HTTP/2 tuning
- HTTP/3 옵션
- connection pool 고도화
- proxy score/health

### 6. Validation & Repair

recipe는 반드시 테스트한다.

검증:

- HTTP status 정상 여부
- item count > 0
- 필수 field 존재
- field type/schema 일치
- 중복률
- 빈 값 비율
- sample output preview

실패하면 failure classifier가 원인을 분류한다.

예:

- `blocked`
- `auth_required`
- `token_expired`
- `pagination_broken`
- `schema_changed`
- `selector_broken`
- `empty_response`
- `rate_limited`
- `proxy_failed`

AI repair loop는 실패 원인과 캡처된 증거를 바탕으로 recipe를 수정한다.

---

## 데이터 흐름

### Discovery flow

```text
input URL + goal
  -> browser probe 실행
  -> network events 수집
  -> DOM/text snapshot 수집
  -> endpoint candidates 추출
  -> AI가 후보 평가
  -> recipe draft 생성
  -> dry-run
  -> validation
  -> recipe 저장
```

### Crawl flow

```text
recipe load
  -> token/cookie 준비
  -> URL frontier 또는 pagination 시작
  -> curl-cffi로 API 요청
  -> response parse
  -> item extract
  -> schema validate
  -> output stream
  -> 실패 시 repair/fallback
```

### Fallback flow

```text
HTTP crawl 실패
  -> 실패 원인 분류
  -> token/cookie 문제면 refresh step 실행
  -> schema 변경이면 sample 재분석
  -> endpoint 변경이면 browser probe 재실행
  -> 차단이면 proxy/fingerprint 조정
  -> 계속 실패하면 browser fallback 또는 사용자에게 보고
```

---

## 초기 패키지 구조 제안

```text
ai-crawler/
  pyproject.toml
  README.md
  src/
    ai_crawler/
      __init__.py
      cli.py
      config.py
      fetchers/
        __init__.py
        curl_cffi_fetcher.py
        types.py
      probe/
        __init__.py
        browser_probe.py
        network_capture.py
        har.py
      inference/
        __init__.py
        endpoint_detector.py
        pagination_detector.py
        schema_inference.py
        recipe_generator.py
      recipes/
        __init__.py
        models.py
        loader.py
        validator.py
      execution/
        __init__.py
        scheduler.py
        runner.py
        rate_limiter.py
        proxy_pool.py
        ban_detection.py
      ai/
        __init__.py
        client.py
        prompts.py
        orchestrator.py
      mcp/
        __init__.py
        server.py
      output/
        __init__.py
        jsonl.py
        csv.py
  tests/
    unit/
    integration/
  .dev/
```

---

## 설계 원칙

1. Browserless first
   - 브라우저는 마지막 수단 또는 분석 도구다.

2. Recipe first
   - 모든 크롤링은 재사용 가능한 recipe로 표현한다.

3. Evidence based AI
   - AI에게 전체 페이지를 무작정 넘기지 않는다.
   - network log, response sample, DOM sample, validation error처럼 압축된 증거만 준다.

4. Deterministic execution
   - AI는 실행 중 매 요청마다 판단하지 않는다.
   - AI는 recipe를 만들고 고친다.
   - 실행 엔진은 가능한 결정론적으로 돈다.

5. Safety and compliance
   - robots.txt, rate limit, user-provided authorization, allowed domain guard를 지원한다.
   - 차단 우회 기능은 합법적/허가된 사용을 전제로 한다.
