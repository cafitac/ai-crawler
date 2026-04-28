# MCP Server Design

## 현재 목표

`ai-crawler`를 Hermes, Claude Code, Codex 같은 MCP 지원 AI agent에 연결한다.

MCP server는 범용 fetch/scrape tool이 아니라 `ai-crawler`의 network-first crawler compiler를 노출하는 thin wrapper다.

핵심 원칙:

- 브라우저는 crawler가 아니라 probe다.
- MCP는 core logic을 직접 갖지 않고 SDK facade를 호출한다.
- CLI, SDK, MCP가 같은 deterministic engine과 report schema를 공유한다.
- CAPTCHA/MFA/Cloudflare/bot challenge 우회 도구를 제공하지 않는다.
- challenge-like 응답은 `challenge_detected`로 분류하고 manual handoff/authorized session이 필요하다고 보고한다.

## 설치/실행

개발 checkout 기준:

```bash
cd /path/to/ai-crawler
uv sync --extra dev --extra mcp --extra http
uv run --extra mcp --extra http ai-crawler mcp
```

패키지 설치 후에는:

```bash
ai-crawler mcp
```

MCP runtime dependency는 optional extra다.

```toml
mcp = ["mcp>=1.0", "curl-cffi>=0.7"]
```

## Client config 생성

CLI가 Hermes / Claude Code / Codex용 snippet을 출력한다.

```bash
ai-crawler mcp-config --client hermes --project /path/to/ai-crawler
ai-crawler mcp-config --client claude-code --project /path/to/ai-crawler
ai-crawler mcp-config --client codex --project /path/to/ai-crawler
```

### Hermes

Hermes는 native MCP client를 지원한다. 설정 파일의 `mcp_servers`에 아래 형태로 추가한다.

```yaml
mcp_servers:
  ai-crawler:
    command: "uv"
    args: ["run", "--project", "/path/to/ai-crawler", "--extra", "mcp", "--extra", "http", "ai-crawler", "mcp"]
    timeout: 300
    connect_timeout: 60
```

Hermes에서 snippet 생성:

```bash
uv run ai-crawler mcp-config --client hermes --project /path/to/ai-crawler
```

### Claude Code / Claude Desktop style JSON

```json
{
  "mcpServers": {
    "ai-crawler": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/ai-crawler",
        "--extra",
        "mcp",
        "--extra",
        "http",
        "ai-crawler",
        "mcp"
      ]
    }
  }
}
```

Snippet 생성:

```bash
uv run ai-crawler mcp-config --client claude-code --project /path/to/ai-crawler
```

### Codex TOML

```toml
[mcp_servers."ai-crawler"]
command = "uv"
args = ["run", "--project", "/path/to/ai-crawler", "--extra", "mcp", "--extra", "http", "ai-crawler", "mcp"]
```

Snippet 생성:

```bash
uv run ai-crawler mcp-config --client codex --project /path/to/ai-crawler
```

## MCP tools

현재 구현된 stdio MCP tools:

### `auto_compile`

Evidence JSON에서 recipe 생성, test, repair, retest를 한 번에 수행한다.
AI harness/agent용 기본 tool이다.

입력:

```json
{
  "evidence_path": "evidence.json",
  "recipe_path": "recipe.yaml",
  "repaired_recipe_path": "repaired.recipe.yaml",
  "test_output_path": "test.jsonl",
  "output_path": "crawl.jsonl",
  "report_path": "auto.report.json",
  "name": "generated-recipe"
}
```

출력은 CLI `ai-crawler auto evidence.json --json`과 같은 report schema다.

### `generate_recipe`

Evidence JSON에서 baseline recipe YAML을 생성한다.

```json
{
  "evidence_path": "evidence.json",
  "output_path": "recipe.yaml",
  "name": "generated-recipe"
}
```

### `test_recipe`

Recipe를 deterministic HTTP runner로 테스트하고 JSONL/report를 작성한다.

```json
{
  "recipe_path": "recipe.yaml",
  "output_path": "test.jsonl",
  "report_path": "report.json"
}
```

### `repair_recipe`

`test_recipe` report를 사용해 recipe를 수리한다.

```json
{
  "recipe_path": "recipe.yaml",
  "report_path": "report.json",
  "output_path": "repaired.recipe.yaml"
}
```

## Python SDK facade

MCP server는 SDK facade를 호출한다.
외부 Python caller도 같은 facade를 사용할 수 있다.

```python
from ai_crawler import AICrawler

crawler = AICrawler()
result = crawler.auto("evidence.json")
print(result.ok)
print(result.exit_code)
print(result.report)
```

테스트에서 네트워크 없이 쓰려면 fetcher를 주입한다.

```python
crawler = AICrawler(fetcher=fake_fetcher)
```

## 검증

기본 검증:

```bash
bash scripts/verify-ai-harness.sh
```

이 스크립트는 SDK/MCP/CLI tests, full pytest, ruff, CLI help, doctor를 실행한다.

MCP `auto_compile`까지 fixture 기반으로 확인하려면:

```bash
uv run --extra http python scripts/smoke-mcp-auto-compile.py
```

이 smoke script는 local fixture site를 띄우고 runtime-independent MCP tool wrapper를 통해 `auto_compile`을 호출한다. 외부 인터넷, 실제 browser, 실제 LLM 없이 `generate -> test -> repair -> retest` 경로와 `crawl.jsonl` 출력을 확인한다.

## 향후 확장

아직 의도적으로 보류한 것:

- HTTP MCP transport
- real browser probe MCP tool
- real LLM provider integration
- long-running job queue
- allowed domain/output sandbox 정책 강제

먼저 stdio MCP + SDK + deterministic auto compiler를 안정화한 뒤 확장한다.
