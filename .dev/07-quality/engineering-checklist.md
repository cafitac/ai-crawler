# Engineering Checklist

## 목적

각 개발 단계에서 놓치면 나중에 비용이 커지는 항목들을 체크리스트로 관리한다.

---

## 설계 체크리스트

- [ ] 브라우저가 execution path에 불필요하게 들어가지 않았는가?
- [ ] AI 호출이 tight crawl loop 안에 들어가지 않았는가?
- [ ] 새 기능이 recipe로 표현 가능한가?
- [ ] 사람이 recipe를 읽고 이해할 수 있는가?
- [ ] 실패 시 failure report가 남는가?
- [ ] secret/token/cookie가 파일에 평문 저장되지 않는가?
- [ ] allowed_domains 또는 URL guard가 있는가?
- [ ] private IP/localhost 접근 정책이 명확한가?

---

## 구현 체크리스트

- [ ] 단위 테스트를 먼저 작성했는가?
- [ ] 외부 네트워크 없이 테스트 가능한가?
- [ ] LLM은 mock으로 대체 가능한가?
- [ ] browser dependency는 optional인가?
- [ ] timeout이 모든 외부 작업에 설정되어 있는가?
- [ ] retry가 무한 루프가 되지 않는가?
- [ ] error message가 사용자가 action을 취할 만큼 구체적인가?
- [ ] logging에 secret이 찍히지 않는가?
- [ ] output path가 sandbox 밖으로 탈출하지 않는가?
- [ ] class/file/module이 하나의 책임만 갖는가?
- [ ] 한 파일에 너무 많은 함수나 클래스가 몰려 있지 않은가?
- [ ] package boundary가 core/adapters/cli/mcp/testing 관심사별로 분리되어 있는가?
- [ ] nullable/None 흐름이 명시적으로 모델링되어 있고 암묵적 None 반환이 없는가?
- [ ] pure function으로 표현 가능한 변환/분석 로직은 FP 스타일로 분리되어 있는가?
- [ ] stateful workflow는 명확한 OOP 객체가 소유하고 있는가?

---

## AI 관련 체크리스트

- [ ] AI output은 structured schema로 검증되는가?
- [ ] unknown action은 reject되는가?
- [ ] malformed output 처리 정책이 있는가?
- [ ] max LLM steps/budget guard가 있는가?
- [ ] prompt injection 방어 문구가 system/developer prompt에 있는가?
- [ ] 웹 페이지 텍스트를 instruction이 아니라 data로 취급하는가?
- [ ] evidence bundle이 raw page 전체보다 충분히 작고 안전한가?
- [ ] AI가 생성한 recipe는 실행 전 validate/dry-run 되는가?

---

## Browser Probe 체크리스트

- [ ] browser process가 정상 종료되는가?
- [ ] probe timeout이 있는가?
- [ ] response body sample 크기 제한이 있는가?
- [ ] image/font/css 등 불필요한 resource를 구분하는가?
- [ ] click/scroll action 실패 시 명확한 error가 있는가?
- [ ] captured cookies/storage를 secret으로 취급하는가?

---

## Execution Engine 체크리스트

- [ ] per-domain concurrency 제한이 있는가?
- [ ] global concurrency 제한이 있는가?
- [ ] rate limiter가 있는가?
- [ ] retry/backoff가 status별로 다른가?
- [ ] 403/429/5xx를 failure classifier로 넘기는가?
- [ ] pagination stop condition이 안전한가?
- [ ] max_pages/max_items/max_seconds guard가 있는가?
- [ ] output streaming 중 중단되어도 partial output이 유효한가?

---

## 릴리즈 전 체크리스트

- [ ] unit/component/e2e test 통과
- [ ] browser integration test 통과
- [ ] MCP smoke test 통과
- [ ] README와 .dev 문서 업데이트
- [ ] 예제 recipe 동작 확인
- [ ] dependency extras 확인
- [ ] secret scan
- [ ] license 확인
