# Crawler Recipe Spec

## 목적

Recipe는 AI가 만든 크롤링 계획을 사람이 읽고, 테스트하고, 재사용할 수 있게 저장하는 선언형 포맷이다.

실행 엔진은 recipe만 보고 deterministic하게 크롤링할 수 있어야 한다.

---

## 파일 형식

기본은 YAML.
추후 JSON도 지원 가능.

파일 위치:

```text
recipes/{site_or_task_name}.yaml
```

---

## 최소 예시

```yaml
version: 1
name: example_products
strategy: network_replay

entry:
  url: https://example.com/products
  allowed_domains:
    - example.com

requests:
  - id: list_products
    method: GET
    url: https://example.com/api/products
    params:
      page: "{{ pagination.page }}"
    headers:
      accept: application/json

pagination:
  type: page_number
  start: 1
  step: 1
  stop_condition: empty_items
  max_pages: 100

extract:
  items_path: $.items
  fields:
    name:
      path: $.name
      type: string
      required: true
    price:
      path: $.price
      type: number
      required: false
    url:
      path: $.url
      type: string
      required: false

execution:
  concurrency: 10
  timeout_seconds: 30
  retries: 3
  retry_backoff: exponential
  impersonate: chrome

output:
  format: jsonl
  path: outputs/example_products.jsonl
```

---

## 주요 섹션

### `version`

Recipe schema version.

### `name`

사람이 읽을 수 있는 recipe 이름.

### `strategy`

초기 값:

- `network_replay`: API/HTTP 요청 재생
- `html_parse`: HTML 문서 파싱
- `browser_fallback`: 브라우저 실행 필요
- `hybrid`: network replay + 일부 browser step

기본 목표는 `network_replay`다.

### `entry`

크롤링 시작점과 도메인 제한.

```yaml
entry:
  url: https://example.com/products
  allowed_domains:
    - example.com
  robots_txt_obey: true
```

### `requests`

실행할 HTTP 요청 정의.

```yaml
requests:
  - id: list_products
    method: GET
    url: https://example.com/api/products
    params:
      page: "{{ pagination.page }}"
    headers:
      accept: application/json
      x-csrf-token: "{{ state.csrf_token }}"
    cookies: inherit
```

### `state`

토큰, 쿠키, CSRF, cursor 같은 동적 값.

```yaml
state:
  csrf_token:
    source: html
    request: entry_page
    selector: 'meta[name="csrf-token"]::attr(content)'
```

### `pagination`

지원할 pagination 유형:

- `page_number`
- `offset_limit`
- `cursor`
- `next_url`
- `infinite_scroll_api`
- `none`

예:

```yaml
pagination:
  type: cursor
  cursor_path: $.pageInfo.endCursor
  has_next_path: $.pageInfo.hasNextPage
  param_name: cursor
```

### `extract`

JSONPath 또는 CSS selector 기반 추출.

JSON API:

```yaml
extract:
  items_path: $.data.products
  fields:
    name:
      path: $.title
      type: string
      required: true
```

HTML:

```yaml
extract:
  items_selector: .product-card
  fields:
    name:
      selector: .product-title::text
      type: string
      required: true
```

### `validation`

결과 품질 검증.

```yaml
validation:
  min_items: 1
  max_empty_ratio:
    name: 0.05
    price: 0.2
  unique_by:
    - url
```

### `execution`

실행 정책.

```yaml
execution:
  backend: curl_cffi
  concurrency: 20
  per_domain_concurrency: 5
  timeout_seconds: 30
  retries: 3
  retry_backoff: exponential
  impersonate: chrome
  http3: false
  proxy_pool: default
```

### `fallback`

실패 시 fallback.

```yaml
fallback:
  on:
    - blocked
    - token_expired
    - schema_changed
  actions:
    - refresh_state
    - browser_probe
    - repair_recipe
```

---

## Recipe lifecycle

```text
draft -> tested -> verified -> production -> broken -> repaired
```

상태는 metadata에 저장한다.

```yaml
metadata:
  status: tested
  created_by: ai
  created_at: 2026-04-27T00:00:00Z
  last_tested_at: 2026-04-27T00:10:00Z
  confidence: 0.87
```

---

## 중요한 원칙

1. Recipe는 사람이 읽을 수 있어야 한다.
2. Recipe는 deterministic하게 실행 가능해야 한다.
3. AI reasoning 전문을 저장하지 말고 summary만 저장한다.
4. 민감한 cookie/token은 recipe 파일에 직접 저장하지 않는다.
5. secret은 secret store 또는 runtime state로 분리한다.
