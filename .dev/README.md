# ai-crawler Development Docs

`ai-crawler`는 AI가 웹사이트의 네트워크/API 구조를 분석하고, 재사용 가능한 crawler recipe를 생성/수정한 뒤, 실제 대량 크롤링은 브라우저 없이 `curl-cffi` 기반 HTTP engine으로 빠르게 실행하는 network-first crawler agent다.

핵심 철학:

```text
Browser is not the crawler. Browser is the probe.
AI is not the request loop. AI is the planner/debugger/recipe author.
```

## 문서 구조

```text
.dev/
  README.md
  01-product/
    decisions.md
    open-source-generality-principles.md
  02-architecture/
    architecture.md
    code-organization-principles.md
  03-ai/
    communication.md
    orchestration.md
    auto-harness-contract.md
  04-mcp/
    server.md
  05-recipe/
    spec.md
  06-implementation/
    roadmap.md
    development-sequence.md
    mvp-plan.md
  07-quality/
    testing-strategy.md
    engineering-checklist.md
  08-operations/
    risks.md
    security-and-compliance.md
    challenge-handling-policy.md
```

## 읽는 순서

1. `01-product/decisions.md`
   - 프로젝트명, 핵심 방향, product positioning 결정

2. `01-product/open-source-generality-principles.md`
   - 기존 agent 계열 OSS 프로젝트에서 가져올 범용성/제품화 원칙

3. `02-architecture/architecture.md`
   - 전체 시스템 구조와 component 역할

4. `02-architecture/code-organization-principles.md`
   - OOP/FP 적용 기준, non-null 설계, 파일/패키지 분리 원칙

5. `03-ai/orchestration.md`
   - AI가 어떤 방식으로 진행을 주도하는지

6. `03-ai/auto-harness-contract.md`
   - AI harness가 호출할 `auto --json` stdout/report schema와 exit code 정책

7. `03-ai/communication.md`
   - LLM Provider, MCP, Agent Adapter 통신 방식

8. `05-recipe/spec.md`
   - AI가 생성하는 crawler recipe 포맷

9. `06-implementation/development-sequence.md`
   - 실제 개발 순서와 각 단계의 exit criteria

10. `07-quality/testing-strategy.md`
   - 테스트 계층, fixture site, mock LLM, integration test 전략

11. `08-operations/risks.md`
   - 기술/법적/운영 리스크

12. `08-operations/challenge-handling-policy.md`
   - CAPTCHA/MFA/Cloudflare-style challenge 감지, manual handoff, authorized session replay 정책

## 최종 사용자 경험

AI harness 자동 모드:

```bash
ai-crawler compile https://example.com/products --goal "collect products" --json
```

Evidence를 사람이 확인/수정해야 하는 경우의 분리 모드:

```bash
ai-crawler probe https://example.com/products --goal "collect products"
ai-crawler auto evidence.json --json
```

일반 CLI 자동 모드:

```bash
ai-crawler compile https://example.com/products --goal "collect products"
```

내부 흐름:

```text
사용자 목표 입력
  -> AgentController가 AI에게 next action 요청
  -> AI가 inspect/probe/generate/test/repair/run 중 하나 선택
  -> Engine이 action 실행
  -> 결과를 evidence로 누적
  -> AI가 evidence를 보고 다음 action 선택
  -> recipe 생성/검증/수정
  -> 검증된 recipe로 deterministic 대량 크롤링
```

수동/단계별 CLI:

```bash
ai-crawler probe https://example.com/products --goal "collect products"
ai-crawler generate-recipe evidence.json
ai-crawler test-recipe recipe.yaml
ai-crawler repair-recipe recipe.yaml
ai-crawler test-recipe repaired.recipe.yaml
ai-crawler run repaired.recipe.yaml
```

MCP 모드:

```bash
ai-crawler mcp-config --client hermes --project /Users/earlypay/Project/ai-crawler
ai-crawler mcp-config --client claude-code --project /Users/earlypay/Project/ai-crawler
ai-crawler mcp-config --client codex --project /Users/earlypay/Project/ai-crawler
ai-crawler mcp
```

현재는 stdio MCP server를 우선 지원한다. HTTP transport는 향후 확장이다.

## 개발 원칙

- Browserless first: 브라우저는 discovery/repair/fallback용이다.
- Recipe first: 모든 자동화 결과는 검증 가능한 recipe로 남긴다.
- AI control plane: AI는 계획/분석/수정에 집중한다.
- Deterministic data plane: 실제 crawl loop는 deterministic engine이 실행한다.
- Evidence-based AI: AI에게 raw page 전체가 아니라 압축된 evidence bundle을 준다.
- Mock-first tests: 기본 테스트는 외부 LLM/API/browser에 의존하지 않는다.
